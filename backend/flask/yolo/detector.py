import numpy as np
from PIL import Image
import io
import base64
from ultralytics import YOLO
import os

class YOLODetector:
    def __init__(self, model_path):
        self.model_path = model_path
        self.model = None
        self.load_model()

        # 类别映射（根据模型实际类别）- 包含详细医疗建议
        self.class_mapping = {
            0: {
                "name": "正常",
                "risk": 5,
                "color": "#28a745",
                "advice": "猫咪排泄物形态正常，建议保持当前饮食和生活方式。",
                "possible_diseases": [],
                "medical_advice": "无需特殊治疗，继续保持良好的饮食和卫生习惯。",
                "medication": "无需用药",
                "prevention": "定期体检、均衡饮食、充足饮水、定期驱虫"
            },
            1: {
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
            },
            2: {
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
            3: {
                "name": "便秘",
                "risk": 40,
                "color": "#17a2b8",
                "advice": "排便困难，建议增加水分摄入并调整饮食。",
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
            4: {
                "name": "寄生虫感染",
                "risk": 75,
                "color": "#dc3545",
                "advice": "严重健康问题，建议立即就医进行专业检查和治疗。",
                "possible_diseases": [
                    "蛔虫感染（最常见）",
                    "绦虫感染（由跳蚤传播）",
                    "球虫感染（Coccidia）",
                    "贾第鞭毛虫（Giardia）",
                    "钩虫感染",
                    "鞭虫感染",
                    "混合寄生虫感染"
                ],
                "medical_advice": "必须就医确诊！需进行粪便浮游检查和镜检确定寄生虫类型。某些寄生虫（如蛔虫、贾第虫）可传染人类，需严格卫生管理。幼猫感染可能导致生长发育迟缓、营养不良甚至死亡。",
                "medication": "广谱驱虫药（吡喹酮：针对绦虫；芬苯达唑：针对蛔虫、钩虫、鞭虫、球虫）；抗原虫药（甲硝唑：针对贾第鞭毛虫）；磺胺类药物（针对球虫）。幼猫：2周龄开始每2周驱虫至12周龄。成猫：每3个月定期驱虫。",
                "prevention": "定期驱虫（室内猫每3-6个月，外出猫每1-3个月）；控制跳蚤（绦虫媒介）；每日清理猫砂盆；避免生食；孕妇避免接触猫粪；定期环境消毒；新猫到家先隔离驱虫"
            }
        }
        self.conf_threshold = 0.001  # 进一步降低置信度阈值以便检测更多目标

    def load_model(self):
        """加载YOLO模型"""
        try:
            print("🚀 加载YOLO模型...")
            print(f"   模型路径: {self.model_path}")

            if os.path.exists(self.model_path):
                file_size = os.path.getsize(self.model_path)
                print(f"   模型文件存在，大小: {file_size/1024/1024:.1f} MB")
                self.model = YOLO(self.model_path)
                print("✅ YOLO模型加载成功！")
            else:
                print(f"❌ 模型文件不存在: {self.model_path}")
                self.model = None

        except Exception as e:
            print(f"❌ 模型加载失败: {e}")
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
            print("❌ YOLO模型未加载")
            return self._create_error_result("Model not loaded")

        try:
            print("   运行YOLO推理...")
            # YOLO可以直接接收PIL图像，不需要转换为numpy
            print(f"   输入图像: {image.size}, mode: {image.mode}")

            results = self.model(image, conf=self.conf_threshold, iou=0.5, imgsz=640, augment=False, verbose=True)
            print(f"   YOLO推理完成，结果数量: {len(results)}")

            if len(results) > 0 and results[0].boxes is not None and len(results[0].boxes) > 0:
                boxes = results[0].boxes
                confidences = boxes.conf.cpu().numpy()
                class_ids = boxes.cls.cpu().numpy()

                print(f"   YOLO检测到 {len(boxes)} 个目标")
                print(f"   所有检测结果:")
                for i, (conf, cls_id) in enumerate(zip(confidences, class_ids)):
                    cls_name = self.class_mapping.get(int(cls_id), {"name": f"类别{int(cls_id)}"})["name"]
                    print(f"     [{i}] 类别: {cls_name} (ID:{int(cls_id)}), 置信度: {conf:.3f}")

                max_idx = np.argmax(confidences)
                class_id = int(class_ids[max_idx])
                confidence = float(confidences[max_idx])

                # 获取类别信息
                class_info = self.class_mapping.get(class_id, self.class_mapping[0])

                # 如果最高置信度也低于 0.4，认为是低置信度检测
                if confidence < 0.4:
                    print(f"⚠️ 低置信度检测: {confidence:.3f} < 0.4，但仍返回检测类别")
                    return self._create_low_confidence_result(class_id, confidence, class_info, len(boxes))
                print(f"🎯 YOLO检测成功: {class_info['name']} (置信度: {confidence:.3f})")
                return self._create_real_result(class_id, confidence, class_info, len(boxes))
            else:
                print("⚠️ YOLO未检测到任何目标")
                print(f"   调试信息: results长度={len(results)}, boxes={results[0].boxes if len(results)>0 else 'N/A'}")
                return self._create_no_detection_result()

        except Exception as e:
            print(f"❌ YOLO检测异常: {e}")
            traceback.print_exc()
            return self._create_error_result(str(e))

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
                "features": f"YOLOv8检测 - {class_info['name']}",
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
                "type": "YOLOv8真实检测",
                "model": os.path.basename(self.model_path),
                "detection_method": "YOLOv8物体检测",
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

    def _create_no_detection_result(self):
        """没有检测到目标时的结果"""
        return {
            "detection": {
                "confidence": 0,
                "class_id": -1,
                "class_name": "未检测到",
                "features": "YOLOv8未在图像中检测到目标",
                "detection_count": 0,
                "is_real_detection": False
            },
            "health_analysis": {
                "risk_level": "unknown",
                "message": "未检测到目标",
                "description": "YOLOv8未在图像中检测到猫咪排泄物，请确保图片清晰可见",
                "confidence": 0,
                "recommendation": "请上传更清晰的猫咪排泄物照片",
                "detected_class": -1
            },
            "risk_metrics": {
                "risk_level": 0,
                "cure_rate": 0,
                "color": "#808080"
            },
            "analysis_info": {
                "type": "YOLOv8真实检测",
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
                "type": "YOLOv8低置信度检测",
                "model": os.path.basename(self.model_path),
                "detection_method": "YOLOv8物体检测(置信度<0.1)",
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
                "type": "YOLOv8检测失败",
                "model": os.path.basename(self.model_path) if self.model_path else "none",
                "detection_method": "检测异常",
                "is_real_ai": False,
                "error": error_msg
            }
        }
