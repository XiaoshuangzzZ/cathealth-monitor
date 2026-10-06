"""
YOLO 糞便特徵偵測器 —— ONNX Runtime 版本。

為什麼從 PyTorch 換成 ONNX
--------------------------
原本用 ultralytics + PyTorch 推論。實測（Windows，本機）：

    import torch + 載入模型        311 MB
    推論一次峰值                   576 MB

Render 的容器記憶體上限是 512 MB，所以模型載入得起來，但一推論就被
OOM kill、服務重啟——使用者看到的是「請求超時」，因為請求永遠沒回應。

改用 onnxruntime 之後：

    建立 session                   140 MB
    推論一次峰值                   242 MB
    推論耗時                       0.34s（PyTorch 是 1.3s）

而且 requirements 不再需要 torch / ultralytics / 5GB 的 CUDA 函式庫，
build 從 5.9GB 降到約 80MB。

關於 rect 前處理（重要）
------------------------
ultralytics 對 PyTorch 模型預設用「矩形推論」：長邊縮到 imgsz，短邊向上取到
stride 的倍數，幾乎不補灰邊。ONNX 若用固定 640x640 就只能補成正方形，
而補出來的灰邊會讓信心分數大幅下降：

    test.jpg  矩形(640x448) → 便秘 0.754
    test.jpg  正方形(640x640，補 96px 灰邊) → 便秘 0.448   ← 差 0.3！

0.448 已經貼近 0.4 的門檻，很容易誤判成「未檢測到」。所以匯出的 ONNX 是
**動態尺寸**，這裡也照樣做矩形前處理，結果才能與原本的 PyTorch 路徑一致
（實測 0.739 vs 0.754）。
"""

import base64
import io
import os
import sys

import numpy as np
from PIL import Image

# 本模組的日誌含有 emoji。Windows 主控台預設是 cp950，印 emoji 會拋
# UnicodeEncodeError；這裡的 print 散落在 load_model() 內，一旦拋出就會被
# 外層 except 接住並把 self.model 設成 None，結果是「模型載入失敗」卻看不出
# 真正原因。
#
# 原本 ultralytics 在 import 時會幫忙把 stdout 轉成 UTF-8，改用 onnxruntime
# 之後那個副作用没了，必須自己處理——否則在非 UTF-8 locale 的環境下載入
# 模型會直接失敗。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

try:
    import onnxruntime as ort
except ImportError:  # 讓錯誤訊息清楚一點，而不是 import 期就炸掉
    ort = None


class YOLODetector:
    def __init__(self, model_path):
        self.model_path = model_path
        self.model = None          # onnxruntime InferenceSession
        self.input_name = None
        self.num_classes = None
        self.imgsz = 640
        self.stride = 32

        # 类别映射（根据模型实际类别）- 包含详细医疗建议
        # 模型实际输出：0=dehydrated_poop, 1=diarrhoea, 2=normal_poop, 3=not_shit, 4=soft_poop
        self.class_mapping = {
            0: {
                "name": "便秘/干硬便便",
                "risk": 40,
                "color": "#17a2b8",
                "advice": "排便困难或粪便干硬，建议增加水分摄入并调整饮食。",
                "possible_diseases": [
                    "饮水不足（最常见）",
                    "毛球症/肠道异物",
                    "慢性肾病（导致脱水）",
                    "巨结肠症（Megacolon）",
                    "骨盆狭窄或骨折愈合后",
                    "低钾血症/高钙血症",
                    "甲状腺功能低下",
                    "肛门直肠炎症或疼痛",
                    "脊椎疾病或神经肌肉问题"
                ],
                "medical_advice": "轻度便秘可尝试家庭护理2-3天。如超过3天未排便、腹部胀痛、呕吐或精神萎靡，需立即就医排除肠梗阻。老年猫和肾病猫需特别警惕。",
                "medication": "渗透性泻剂（聚乙二醇3350/MiraLax：1/4-1/2茶匙每日1-2次；乳果糖：0.5-1.0ml/kg每8-12小时）；促肠蠕动药（西沙必利：2.5-5mg每8小时，需处方）；灌肠（温水或开塞露，严重时需兽医操作）。绝对禁止使用含磷酸盐的灌肠剂！",
                "prevention": "增加饮水（多放饮水点、使用流动饮水机、改喂湿粮）；定期梳毛减少毛球；高纤维饮食（南瓜泥1-4茶匙/餐）；保持理想体重；定期运动促进肠道蠕动"
            },
            1: {
                "name": "拉稀",
                "risk": 65,
                "color": "#fd7e14",
                "advice": "严重肠道问题，建议尽快就医检查。",
                "possible_diseases": [
                    "细菌性肠炎（沙门氏菌、大肠杆菌）",
                    "病毒感染（猫瘟/泛白细胞减少症、冠状病毒）",
                    "寄生虫感染（球虫、贾第鞭毛虫）",
                    "炎症性肠病（IBD）",
                    "胰腺炎",
                    "甲状腺功能亢进（老年猫）",
                    "食物中毒",
                    "肠道异物"
                ],
                "medical_advice": "建议24小时内就医！腹泻会导致快速脱水和电解质失衡，幼猫尤其危险。就医前禁食6-12小时（不禁水），保留粪便样本供检查。如便血、高烧、呕吐或精神极度萎靡需急诊。",
                "medication": "抗生素（需兽医处方：恩诺沙星、甲硝唑）；止泻药（蒙脱石散短期使用）；驱虫药（针对球虫：芬苯达唑/磺胺类药物；针对贾第虫：甲硝唑）；益生菌；严重时需静脉输液。",
                "prevention": "避免生食；定期驱虫（每3个月）；接种疫苗（猫瘟）；保持环境清洁；避免接触病猫；新猫到家隔离观察"
            },
            2: {
                "name": "正常",
                "risk": 5,
                "color": "#28a745",
                "advice": "猫咪排泄物形态正常，建议保持当前饮食和生活方式。",
                "possible_diseases": [],
                "medical_advice": "无需特殊治疗，继续保持良好的饮食和卫生习惯。",
                "medication": "无需用药",
                "prevention": "定期体检、均衡饮食、充足饮水、定期驱虫"
            },
            3: {
                "name": "未检测到排泄物",
                "risk": 0,
                "color": "#808080",
                "advice": "图片中未识别到猫咪排泄物，请上传清晰的猫咪排泄物照片。",
                "possible_diseases": [],
                "medical_advice": "请重新拍摄更清晰的猫咪排泄物照片，确保粪便位于画面中央且光线充足。",
                "medication": "无需用药",
                "prevention": "拍摄时避免杂物干扰，确保画面主体为猫咪排泄物"
            },
            4: {
                "name": "软便",
                "risk": 25,
                "color": "#ffc107",
                "advice": "轻度肠道不适，建议观察饮食并适当调整。",
                "possible_diseases": [
                    "饮食不当/突然换粮",
                    "食物过敏或不耐受",
                    "轻度肠道菌群失调",
                    "压力或环境改变引起",
                    "早期寄生虫感染",
                    "轻微肠炎"
                ],
                "medical_advice": "建议观察24-48小时。如持续超过3天，或伴随食欲不振、精神萎靡，建议就医进行粪便检查。",
                "medication": "益生菌（如宠物专用益生菌粉）；如怀疑寄生虫需使用驱虫药（芬苯达唑）。禁食12小时后给予清淡饮食（白水煮鸡胸肉+少量米饭）。",
                "prevention": "遵循7-10天换粮法；避免喂食人类食物；定期驱虫；减少环境压力；保持猫砂盆清洁"
            }
        }
        self.conf_threshold = 0.25  # 过滤低置信度噪声，避免随机结果
        self.iou_threshold = 0.5

        self.load_model()

    # ========== 模型載入 ==========

    def load_model(self):
        """建立 ONNX Runtime session。"""
        try:
            print("🚀 載入 ONNX 模型...")
            print(f"   模型路徑: {self.model_path}")

            if ort is None:
                print("❌ 未安裝 onnxruntime")
                self.model = None
                return

            if not os.path.exists(self.model_path):
                print(f"❌ 模型檔案不存在: {self.model_path}")
                self.model = None
                return

            size = os.path.getsize(self.model_path)
            print(f"   模型檔案存在，大小: {size/1024/1024:.1f} MB")

            opts = ort.SessionOptions()
            # 單執行緒：容器 CPU 配額有限，開多執行緒只是增加記憶體與排程開銷
            opts.intra_op_num_threads = int(os.environ.get("ORT_THREADS", "1"))
            opts.inter_op_num_threads = 1
            opts.log_severity_level = 3
            # 預設關閉 CPU memory arena。實測（本機，載入模型後連續推論）：
            #     arena 開啟  常駐 344 MB   每次 0.37-0.39s
            #     arena 關閉  常駐 169 MB   每次 0.37-0.40s
            # 省下 175MB 而速度幾乎無損，對 512MB 的容器上限來說非常值得。
            # 設 ORT_MEM_ARENA=1 可改回預設行為。
            if os.environ.get("ORT_MEM_ARENA") != "1":
                opts.enable_cpu_mem_arena = False

            self.model = ort.InferenceSession(
                self.model_path, opts, providers=["CPUExecutionProvider"]
            )

            inp = self.model.get_inputs()[0]
            self.input_name = inp.name
            if isinstance(inp.shape[2], int):
                self.imgsz = inp.shape[2]
            out = self.model.get_outputs()[0]
            self.num_classes = out.shape[1] - 4

            print(f"✅ ONNX 模型載入成功！(imgsz={self.imgsz}, classes={self.num_classes})")

        except Exception as e:
            print(f"❌ 模型載入失敗: {type(e).__name__}: {e}")
            self.model = None

    def base64_to_image(self, base64_string):
        """Base64转图片"""
        try:
            if base64_string.startswith('data:image'):
                base64_string = base64_string.split(',')[1]
            image_data = base64.b64decode(base64_string)
            image = Image.open(io.BytesIO(image_data))
            return image.convert('RGB')
        except Exception as e:
            print(f"❌ 图像解码失败: {e}")
            return None

    # ========== 前處理 / 後處理 ==========

    def _rect_shape(self, image):
        """矩形推論的目標尺寸：長邊縮到 imgsz，短邊向上取到 stride 的倍數。

        這對應 ultralytics 的 LetterBox(auto=True)。補得越少，信心分數越接近
        訓練時的分佈——正方形補滿灰邊會讓信心掉約 0.3。
        """
        iw, ih = image.size
        r = min(self.imgsz / iw, self.imgsz / ih)
        nw = min(self.imgsz, int(np.ceil(iw * r / self.stride) * self.stride))
        nh = min(self.imgsz, int(np.ceil(ih * r / self.stride) * self.stride))
        return nh, nw

    def _letterbox(self, image, target, color=114):
        """等比縮放 + 置中灰邊填充，回傳 NCHW float32 (0-1)。"""
        h, w = target
        iw, ih = image.size
        r = min(w / iw, h / ih)
        nw, nh = round(iw * r), round(ih * r)
        resized = image.resize((nw, nh), Image.BILINEAR)
        canvas = Image.new("RGB", (w, h), (color, color, color))
        canvas.paste(resized, ((w - nw) // 2, (h - nh) // 2))

        a = np.asarray(canvas, dtype=np.float32) / 255.0
        return np.ascontiguousarray(np.transpose(a, (2, 0, 1))[None, ...])

    @staticmethod
    def _nms(boxes, scores, iou_thres):
        """純 numpy 的 NMS（原本由 torchvision 提供）。"""
        order = scores.argsort()[::-1]
        keep = []
        while order.size > 0:
            i = order[0]
            keep.append(i)
            if order.size == 1:
                break
            xx1 = np.maximum(boxes[i, 0], boxes[order[1:], 0])
            yy1 = np.maximum(boxes[i, 1], boxes[order[1:], 1])
            xx2 = np.minimum(boxes[i, 2], boxes[order[1:], 2])
            yy2 = np.minimum(boxes[i, 3], boxes[order[1:], 3])
            w = np.maximum(0.0, xx2 - xx1)
            h = np.maximum(0.0, yy2 - yy1)
            inter = w * h
            area_i = (boxes[i, 2] - boxes[i, 0]) * (boxes[i, 3] - boxes[i, 1])
            area_o = ((boxes[order[1:], 2] - boxes[order[1:], 0]) *
                      (boxes[order[1:], 3] - boxes[order[1:], 1]))
            iou = inter / (area_i + area_o - inter + 1e-9)
            order = order[1:][iou <= iou_thres]
        return keep

    def _run_inference(self, image):
        """執行推論，回傳 (class_ids, confidences)，依信心由高到低排序。"""
        target = self._rect_shape(image)
        x = self._letterbox(image, target)

        out = self.model.run(None, {self.input_name: x})[0]
        pred = out[0]
        # (4+nc, anchors) -> (anchors, 4+nc)
        if pred.shape[0] < pred.shape[1]:
            pred = pred.T

        boxes_xywh = pred[:, :4]
        scores_all = pred[:, 4:]
        cls_ids = scores_all.argmax(axis=1)
        confs = scores_all[np.arange(len(cls_ids)), cls_ids]

        # 先用較低的門檻篩掉絕大多數 anchor，再做 NMS
        keep = confs > 0.01
        boxes_xywh, confs, cls_ids = boxes_xywh[keep], confs[keep], cls_ids[keep]

        if len(confs) == 0:
            return np.array([]), np.array([])

        cx, cy, w, h = boxes_xywh.T
        boxes = np.stack([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], axis=1)
        idx = self._nms(boxes, confs, self.iou_threshold)

        order = np.argsort(-confs[idx])
        idx = np.asarray(idx)[order]
        return cls_ids[idx], confs[idx]

    # ========== 主要檢測函式 ==========

    def detect_stool_features(self, image):
        """主要的检测函数 - 仅使用真实YOLO检测"""
        import traceback
        print("\n" + "="*50)
        print("🔍 开始YOLO检测...")
        print(f"   输入图片尺寸: {image.size}")
        print(f"   输入图片模式: {image.mode}")

        # 保存调试图片
        try:
            debug_path = "debug_last_input.jpg"
            image.save(debug_path)
            print(f"   已保存调试图片: {debug_path}")
        except Exception as e:
            print(f"   保存调试图片失败: {e}")

        if self.model is None:
            print("❌ 模型未加载")
            return self._create_error_result("Model not loaded")

        try:
            target = self._rect_shape(image)
            print(f"   矩形前處理: {image.size} -> {target[1]}x{target[0]}（不補灰邊）")
            print("   运行ONNX推理...")

            class_ids, confidences = self._run_inference(image)

            if len(confidences) == 0:
                print("⚠️ 未检测到任何目标")
                return self._create_no_detection_result()

            print(f"   YOLO检测到 {len(confidences)} 个目标")
            for i, (conf, cls_id) in enumerate(zip(confidences, class_ids)):
                cls_name = self.class_mapping.get(int(cls_id), {"name": f"类别{int(cls_id)}"})["name"]
                print(f"     [{i}] 类别: {cls_name} (ID:{int(cls_id)}), 置信度: {conf:.3f}")

            class_id = int(class_ids[0])
            confidence = float(confidences[0])
            good_boxes = int((confidences > self.conf_threshold).sum())

            class_info = self.class_mapping.get(class_id, self.class_mapping[0])

            # 低于 0.4 认为没有检测到清晰目标，避免给用户一个随机/不可靠的结果
            if confidence < 0.4:
                print(f"⚠️ 置信度太低: {confidence:.3f} < 0.4，返回未检测到")
                return self._create_no_detection_result(
                    reason=f"AI检测到疑似目标，但置信度仅{confidence:.1%}，不足以给出准确判断"
                )
            print(f"🎯 YOLO检测成功: {class_info['name']} (置信度: {confidence:.3f})")
            return self._create_real_result(class_id, confidence, class_info, good_boxes)

        except Exception as e:
            print(f"❌ YOLO检测异常: {e}")
            traceback.print_exc()
            return self._create_error_result(str(e))

    # ========== 結果建構（與原本一致）==========

    def _create_real_result(self, class_id, confidence, class_info, detection_count):
        """创建真实的YOLO检测结果"""
        risk_level = "normal" if class_info["risk"] <= 30 else "warning" if class_info["risk"] <= 50 else "danger"

        # 构建详细的医疗建议
        detailed_advice = self._build_detailed_advice(class_info, confidence)

        return {
            "detection": {
                "confidence": round(confidence, 3),
                "class_id": class_id,
                "class_name": class_info["name"],
                "features": f"YOLOv11检测 - {class_info['name']}",
                "detection_count": detection_count,
                "is_real_detection": True
            },
            "health_analysis": {
                "risk_level": risk_level,
                "message": f"检测到: {class_info['name']}",
                "description": detailed_advice["description"],
                "confidence": round(confidence, 3),
                "recommendation": class_info["advice"],
                "detected_class": class_id,
                "detailed_advice": detailed_advice
            },
            "risk_metrics": {
                "risk_level": class_info["risk"],
                "cure_rate": 100 - class_info["risk"],
                "color": class_info["color"]
            },
            "analysis_info": {
                "type": "YOLOv11真实检测",
                "model": os.path.basename(self.model_path),
                "detection_method": "YOLOv11 ONNX Runtime 物体检测",
                "is_real_ai": True
            }
        }

    def _build_detailed_advice(self, class_info, confidence):
        """构建详细的医疗建议"""
        risk = class_info["risk"]

        if risk <= 10:
            urgency = "无需担忧"
            visit_advice = "无需就医，继续观察即可"
        elif risk <= 30:
            urgency = "轻度关注"
            visit_advice = "暂时无需就医，但需持续观察2-3天。如症状持续或加重，建议就医。"
        elif risk <= 50:
            urgency = "建议就医"
            visit_advice = "建议3天内就医检查，特别是症状持续或伴随其他异常时。"
        elif risk <= 70:
            urgency = "尽快就医"
            visit_advice = "建议24-48小时内就医，进行专业检查和治疗。"
        else:
            urgency = "紧急就医"
            visit_advice = "建议立即就医！此情况可能危及生命，需紧急处理。"

        return {
            "description": f"AI分析结果为{class_info['name']}，风险指数{risk}%。{class_info['advice']}",
            "possible_diseases": class_info.get("possible_diseases", []),
            "medical_advice": class_info.get("medical_advice", "请咨询兽医师"),
            "medication": class_info.get("medication", "需兽医处方"),
            "prevention": class_info.get("prevention", "保持健康生活习惯"),
            "urgency_level": urgency,
            "visit_advice": visit_advice,
            "risk_assessment": f"风险指数: {risk}% - {'低风险' if risk <= 30 else '中风险' if risk <= 60 else '高风险'}"
        }

    def _create_no_detection_result(self, reason=None):
        """没有检测到目标时的结果"""
        default_reason = "YOLOv11未在图像中检测到猫咪排泄物，请上传清晰的猫咪排泄物照片"
        display_reason = reason or default_reason
        return {
            "detection": {
                "confidence": 0,
                "class_id": -1,
                "class_name": "未检测到排泄物",
                "features": display_reason,
                "detection_count": 0,
                "is_real_detection": False
            },
            "health_analysis": {
                "risk_level": "unknown",
                "message": "未检测到排泄物",
                "description": display_reason,
                "confidence": 0,
                "recommendation": "请上传更清晰的猫咪排泄物照片，确保粪便位于画面中央、光线充足",
                "detected_class": -1
            },
            "risk_metrics": {
                "risk_level": 0,
                "cure_rate": 0,
                "color": "#808080"
            },
            "analysis_info": {
                "type": "YOLOv11真实检测",
                "model": os.path.basename(self.model_path),
                "detection_method": "未检测到目标",
                "is_real_ai": True
            }
        }

    def _create_low_confidence_result(self, class_id, actual_confidence, class_info, detection_count):
        """低置信度时的结果 - 返回检测到的类别但提示用户"""
        risk_level = "normal" if class_info["risk"] <= 30 else "warning" if class_info["risk"] <= 50 else "danger"
        detailed_advice = self._build_detailed_advice(class_info, actual_confidence)

        return {
            "detection": {
                "confidence": round(actual_confidence, 3),
                "class_id": class_id,
                "class_name": class_info["name"],
                "features": f"AI检测到{class_info['name']}，但置信度较低，建议上传更清晰的图片",
                "detection_count": detection_count,
                "is_real_detection": True,
                "low_confidence": True
            },
            "health_analysis": {
                "risk_level": risk_level,
                "message": f"{class_info['name']} ({actual_confidence:.1%})",
                "description": f"AI检测到{class_info['name']}，置信度{actual_confidence:.1%}。建议上传更清晰的猫咪排泄物照片以获得更准确的结果。",
                "confidence": round(actual_confidence, 3),
                "recommendation": class_info["advice"] + " (建议上传更清晰的图片以确认)",
                "detected_class": class_id,
                "detailed_advice": detailed_advice
            },
            "risk_metrics": {
                "risk_level": class_info["risk"],
                "cure_rate": 100 - class_info["risk"],
                "color": class_info["color"]
            },
            "analysis_info": {
                "type": "YOLOv11低置信度检测",
                "model": os.path.basename(self.model_path),
                "detection_method": "YOLOv11物体检测(置信度<0.1)",
                "is_real_ai": True,
                "actual_confidence": round(actual_confidence, 3)
            }
        }

    def _create_error_result(self, error_msg):
        """检测出错时的结果"""
        return {
            "detection": {
                "confidence": 0,
                "class_id": -1,
                "class_name": "检测失败",
                "features": f"检测出错: {error_msg}",
                "detection_count": 0,
                "is_real_detection": False
            },
            "health_analysis": {
                "risk_level": "error",
                "message": "检测失败",
                "description": f"YOLO检测过程中出现错误: {error_msg}",
                "confidence": 0,
                "recommendation": "请稍后重试或联系管理员",
                "detected_class": -1
            },
            "risk_metrics": {
                "risk_level": 0,
                "cure_rate": 0,
                "color": "#dc3545"
            },
            "analysis_info": {
                "type": "YOLOv11检测失败",
                "model": os.path.basename(self.model_path) if self.model_path else "none",
                "detection_method": "检测异常",
                "is_real_ai": False,
                "error": error_msg
            }
        }
