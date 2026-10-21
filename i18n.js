/*!
 * CatHealth Monitor - 多語言 / Internationalisation
 * 支援：繁體中文 (zh-TW)、简体中文 (zh-CN)、English (en)、Português (pt)
 *
 * 設計：
 * - 以目前介面上的中文原文作為翻譯鍵，自動翻譯 DOM 文字節點與屬性，
 *   因此不必為每一段 HTML 加上 data-i18n 屬性。
 * - MutationObserver 會處理 JS 動態產生的內容。
 * - 使用者輸入的內容請加上 data-i18n-skip，避免被誤翻。
 */
(function (global) {
    'use strict';

    var STORAGE_KEY = 'cathealth_lang';
    var DEFAULT_LANG = 'zh-CN';
    var SUPPORTED = ['zh-TW', 'zh-CN', 'en', 'pt'];
    var HTML_LANG = { 'zh-TW': 'zh-Hant', 'zh-CN': 'zh-Hans', 'en': 'en', 'pt': 'pt' };

    /*
     * 字典格式：
     *   以介面中文原文為鍵；cn 僅在原文是繁體時提供（切到簡中時轉換用）。
     *   tw = 繁體中文、en = English、pt = Português。
     */
    var DICT = {

        /* ==================== 導航 / 頁面標題 ==================== */
        '控制面板': { tw: '控制面板', en: 'Dashboard', pt: 'Painel' },
        'AI排泄物分析': { tw: 'AI排泄物分析', en: 'AI Waste Analysis', pt: 'Análise de dejetos com IA' },
        '猫咪档案': { tw: '貓咪檔案', en: 'Cat Profiles', pt: 'Perfis dos gatos' },
        '健康评估': { tw: '健康評估', en: 'Health Assessment', pt: 'Avaliação de saúde' },
        '健康评估问卷': { tw: '健康評估問卷', en: 'Health Questionnaire', pt: 'Questionário de saúde' },
        '附近医院': { tw: '附近醫院', en: 'Nearby Hospitals', pt: 'Hospitais próximos' },
        '设置': { tw: '設定', en: 'Settings', pt: 'Definições' },
        '登出': { tw: '登出', en: 'Log out', pt: 'Terminar sessão' },
        '主要功能': { tw: '主要功能', en: 'Main Features', pt: 'Funcionalidades principais' },
        '语言': { tw: '語言', en: 'Language', pt: 'Idioma' },

        /* ==================== 品牌 / 通用 ==================== */
        '猫咪健康管理中心': { tw: '貓咪健康管理中心', en: 'Cat Health Management Centre', pt: 'Centro de Gestão da Saúde Felina' },
        '猫咪健康管理中心 - CatHealth': { tw: '貓咪健康管理中心 - CatHealth', en: 'CatHealth - Cat Health Management Centre', pt: 'CatHealth - Centro de Gestão da Saúde Felina' },
        '猫咪家长': { tw: '貓咪家長', en: 'Cat parent', pt: 'Tutor do gato' },
        '欢迎使用': { tw: '歡迎使用', en: 'Welcome', pt: 'Bem-vindo' },
        '欢迎回来！': { tw: '歡迎回來！', en: 'Welcome back!', pt: 'Bem-vindo de volta!' },
        '欢迎回来，{name}！': { tw: '歡迎回來，{name}！', en: 'Welcome back, {name}!', pt: 'Bem-vindo de volta, {name}!' },
        '从智能分析开始，守护爱宠健康': { tw: '從智能分析開始，守護愛寵健康', en: "Start with smart analysis to protect your pet's health", pt: 'Comece com uma análise inteligente para proteger a saúde do seu animal' },
        '未知品种': { tw: '未知品種', en: 'Unknown breed', pt: 'Raça desconhecida' },
        '未知年龄': { tw: '未知年齡', en: 'Unknown age', pt: 'Idade desconhecida' },
        '未知错误': { tw: '未知錯誤', en: 'Unknown error', pt: 'Erro desconhecido' },
        '重试': { tw: '重試', en: 'Retry', pt: 'Tentar novamente' },

        /* ==================== 主頁 ==================== */
        'AI分析': { tw: 'AI分析', en: 'AI Analysis', pt: 'Análise com IA' },
        '健康指数': { tw: '健康指數', en: 'Health Index', pt: 'Índice de saúde' },
        '饮食': { tw: '飲食', en: 'Diet', pt: 'Alimentação' },
        '活动': { tw: '活動', en: 'Activity', pt: 'Atividade' },
        '体重': { tw: '體重', en: 'Weight', pt: 'Peso' },
        '我的猫咪': { tw: '我的貓咪', en: 'My Cats', pt: 'Os meus gatos' },

        /* ==================== AI 分析 ==================== */
        'AI排泄物智能分析': { tw: 'AI排泄物智能分析', en: 'Smart AI Waste Analysis', pt: 'Análise inteligente de dejetos com IA' },
        '基于YOLOv11模型的智能识别，快速分析猫咪健康状态': { tw: '基於YOLOv11模型的智能識別，快速分析貓咪健康狀態', en: 'YOLOv11-powered recognition for a quick analysis of your cat\'s health', pt: 'Reconhecimento com YOLOv11 para uma análise rápida da saúde do gato' },
        '上传分析图片': { tw: '上傳分析圖片', en: 'Upload an Image', pt: 'Carregar uma imagem' },
        '上传猫咪排泄物照片，AI自动分析健康状态并提供专业建议': { tw: '上傳貓咪排泄物照片，AI自動分析健康狀態並提供專業建議', en: "Upload a photo of your cat's waste; AI will analyse its health and give professional advice", pt: 'Carregue uma foto dos dejetos do gato; a IA analisará a saúde e dará conselhos profissionais' },
        '点击上传或拖拽图片到此区域': { tw: '點擊上傳或拖曳圖片到此區域', en: 'Click to upload or drag an image here', pt: 'Clique para carregar ou arraste uma imagem para aqui' },
        '支持 JPG、PNG 格式，最大 5MB': { tw: '支援 JPG、PNG 格式，最大 5MB', en: 'Supports JPG and PNG, up to 5 MB', pt: 'Suporta JPG e PNG, até 5 MB' },
        '支持 JPG、PNG 格式': { tw: '支援 JPG、PNG 格式', en: 'Supports JPG and PNG', pt: 'Suporta JPG e PNG' },
        '选择图片': { tw: '選擇圖片', en: 'Choose Image', pt: 'Escolher imagem' },
        'YOLOv11 AI分析中...': { tw: 'YOLOv11 AI分析中...', en: 'YOLOv11 AI analysing...', pt: 'IA YOLOv11 a analisar...' },
        '正在使用智能图片识别系统': { tw: '正在使用智能圖片識別系統', en: 'Using the intelligent image recognition system', pt: 'A utilizar o sistema inteligente de reconhecimento de imagens' },
        '分析失败': { tw: '分析失敗', en: 'Analysis failed', pt: 'Falha na análise' },
        '分析失败: {msg}': { tw: '分析失敗：{msg}', en: 'Analysis failed: {msg}', pt: 'Falha na análise: {msg}' },
        '请求超时': { tw: '請求逾時', en: 'Request timed out', pt: 'Tempo de pedido esgotado' },
        'Render 免费版唤醒需要 30-60 秒，请重新尝试。': { tw: 'Render 免費方案喚醒需要 30–60 秒，請重新嘗試。', en: 'The Render free tier takes 30–60 seconds to wake up. Please try again.', pt: 'O plano gratuito do Render leva 30–60 segundos a acordar. Tente novamente.' },
        '无法连接到后端服务': { tw: '無法連接到後端服務', en: 'Cannot connect to the backend service', pt: 'Não foi possível ligar ao serviço backend' },
        '可能原因：': { tw: '可能原因：', en: 'Possible reasons:', pt: 'Possíveis motivos:' },
        '1. 后端正在启动中（Render 免费版刚唤醒）': { tw: '1. 後端正在啟動中（Render 免費方案剛喚醒）', en: '1. The backend is starting (Render free tier waking up)', pt: '1. O backend está a iniciar (plano gratuito do Render a acordar)' },
        '2. 手机网络不稳定': { tw: '2. 手機網絡不穩定', en: '2. Unstable mobile network', pt: '2. Rede móvel instável' },
        '3. 后端服务暂时不可用': { tw: '3. 後端服務暫時不可用', en: '3. The backend service is temporarily unavailable', pt: '3. O serviço backend está temporariamente indisponível' },
        '重新尝试': { tw: '重新嘗試', en: 'Try Again', pt: 'Tentar novamente' },
        '分析结果（模拟数据）': { tw: '分析結果（模擬資料）', en: 'Analysis Result (Simulated Data)', pt: 'Resultado da análise (dados simulados)' },
        'AI分析结果': { tw: 'AI分析結果', en: 'AI Analysis Result', pt: 'Resultado da análise de IA' },
        '健康状态': { tw: '健康狀態', en: 'Health Status', pt: 'Estado de saúde' },
        '置信度': { tw: '置信度', en: 'Confidence', pt: 'Confiança' },
        '风险等级': { tw: '風險等級', en: 'Risk Level', pt: 'Nível de risco' },
        '治愈概率': { tw: '治癒概率', en: 'Recovery Probability', pt: 'Probabilidade de recuperação' },
        '检测特征': { tw: '檢測特徵', en: 'Detection Features', pt: 'Características detetadas' },
        '健康建议': { tw: '健康建議', en: 'Health Advice', pt: 'Conselhos de saúde' },
        '免责声明：': { tw: '免責聲明：', en: 'Disclaimer: ', pt: 'Aviso: ' },
        '本分析结果由 AI 模型/模拟算法自动生成，仅供参考， 不构成医疗诊断。请勿据此自行用药，如有异常请咨询专业兽医。': {
            tw: '本分析結果由 AI 模型／模擬演算法自動產生，僅供參考，不構成醫療診斷。請勿據此自行用藥，如有異常請諮詢專業獸醫。',
            en: 'This result was generated automatically by an AI model/simulation algorithm for reference only and is not a medical diagnosis. Do not self-medicate based on it; consult a vet if anything seems wrong.',
            pt: 'Este resultado foi gerado automaticamente por um modelo de IA/algoritmo de simulação apenas para referência e não constitui um diagnóstico médico. Não se automedique com base nele; consulte um veterinário se algo parecer errado.'
        },
        '分析新图片': { tw: '分析新圖片', en: 'Analyse New Image', pt: 'Analisar nova imagem' },
        '颜色': { tw: '顏色', en: 'Colour', pt: 'Cor' },
        '质地': { tw: '質地', en: 'Texture', pt: 'Textura' },
        '形状': { tw: '形狀', en: 'Shape', pt: 'Forma' },

        /* 模擬數據警示（原文為繁體） */
        '本次結果為模擬數據，不是 AI 模型輸出': { cn: '本次结果为模拟数据，不是 AI 模型输出', tw: '本次結果為模擬數據，不是 AI 模型輸出', en: 'This result is simulated data, not AI model output', pt: 'Este resultado são dados simulados, não a saída de um modelo de IA' },
        '後端的 YOLO 模型目前無法使用，以下數據由隨機模擬演算法產生，': { cn: '后端的 YOLO 模型目前无法使用，以下数据由随机模拟算法产生，', tw: '後端的 YOLO 模型目前無法使用，以下數據由隨機模擬演算法產生，', en: 'The backend YOLO model is currently unavailable. The data below comes from a random simulation algorithm,', pt: 'O modelo YOLO do backend está indisponível. Os dados abaixo provêm de um algoritmo de simulação aleatória,' },
        '不具任何診斷意義': { cn: '不具任何诊断意义', tw: '不具任何診斷意義', en: 'and has no diagnostic value', pt: 'e não tem qualquer valor de diagnóstico' },
        '，請勿據此判斷貓咪健康狀況。': { cn: '，请勿据此判断猫咪健康状况。', tw: '，請勿據此判斷貓咪健康狀況。', en: '. Do not use it to judge your cat\'s health.', pt: '. Não o utilize para avaliar a saúde do seu gato.' },
        '請將此情況回報給開發者，或開啟': { cn: '请将此情况报告给开发者，或打开', tw: '請將此情況回報給開發者，或開啟', en: 'Please report this to the developer, or open', pt: 'Comunique este problema ao programador ou abra' },
        '查看模型狀態。': { cn: '查看模型状态。', tw: '查看模型狀態。', en: 'to check the model status.', pt: 'para ver o estado do modelo.' },

        /* ==================== 貓咪檔案 ==================== */
        '猫咪档案管理': { tw: '貓咪檔案管理', en: 'Cat Profile Management', pt: 'Gestão dos perfis dos gatos' },
        '管理您的爱猫信息，支持多猫家庭': { tw: '管理您的愛貓資訊，支援多貓家庭', en: "Manage your cats' information, with support for multi-cat households", pt: 'Gira a informação dos seus gatos, com suporte para vários gatos' },
        '添加新猫咪': { tw: '新增貓咪', en: 'Add New Cat', pt: 'Adicionar novo gato' },
        '还没有添加猫咪': { tw: '尚未新增貓咪', en: 'No cats added yet', pt: 'Ainda não há gatos adicionados' },
        '点击"猫咪档案"添加您的第一只猫咪': { tw: '點擊「貓咪檔案」新增您的第一隻貓咪', en: 'Go to "Cat Profiles" to add your first cat', pt: 'Vá a "Perfis dos gatos" para adicionar o seu primeiro gato' },
        '点击上方按钮添加您的第一只猫咪': { tw: '點擊上方按鈕新增您的第一隻貓咪', en: 'Use the button above to add your first cat', pt: 'Utilize o botão acima para adicionar o seu primeiro gato' },
        '编辑': { tw: '編輯', en: 'Edit', pt: 'Editar' },
        '详情': { tw: '詳情', en: 'Details', pt: 'Detalhes' },
        '编辑信息': { tw: '編輯資訊', en: 'Edit Info', pt: 'Editar informação' },
        '健康详情': { tw: '健康詳情', en: 'Health Details', pt: 'Detalhes de saúde' },
        '健康': { tw: '健康', en: 'Healthy', pt: 'Saudável' },
        '状态': { tw: '狀態', en: 'Status', pt: 'Estado' },
        '性别': { tw: '性別', en: 'Gender', pt: 'Sexo' },
        '年龄': { tw: '年齡', en: 'Age', pt: 'Idade' },
        '品种': { tw: '品種', en: 'Breed', pt: 'Raça' },
        '备注': { tw: '備註', en: 'Notes', pt: 'Notas' },
        '更换照片': { tw: '更換照片', en: 'Change photo', pt: 'Alterar foto' },
        '删除猫咪': { tw: '刪除貓咪', en: 'Delete cat', pt: 'Eliminar gato' },
        '确定要删除这只猫咪吗？此操作无法撤销。': { tw: '確定要刪除這隻貓咪嗎？此操作無法復原。', en: 'Delete this cat? This cannot be undone.', pt: 'Eliminar este gato? Esta ação não pode ser anulada.' },
        '请输入猫咪名字': { tw: '請輸入貓咪名字', en: "Please enter the cat's name", pt: 'Introduza o nome do gato' },
        '请先登录再添加猫咪': { tw: '請先登入再新增貓咪', en: 'Please sign in before adding a cat', pt: 'Inicie sessão antes de adicionar um gato' },
        '✅ 猫咪添加成功！': { tw: '✅ 貓咪新增成功！', en: '✅ Cat added!', pt: '✅ Gato adicionado!' },
        '添加失败: {msg}': { tw: '新增失敗：{msg}', en: 'Add failed: {msg}', pt: 'Falha ao adicionar: {msg}' },
        '添加失败，请检查网络连接': { tw: '新增失敗，請檢查網絡連線', en: 'Add failed. Check your network connection.', pt: 'Falha ao adicionar. Verifique a ligação à rede.' },
        '✅ 猫咪照片更新成功！': { tw: '✅ 貓咪照片更新成功！', en: '✅ Cat photo updated!', pt: '✅ Foto do gato atualizada!' },
        '✅ 健康信息更新成功！': { tw: '✅ 健康資訊更新成功！', en: '✅ Health information updated!', pt: '✅ Informações de saúde atualizadas!' },
        '更新失败: {msg}': { tw: '更新失敗：{msg}', en: 'Update failed: {msg}', pt: 'Falha ao atualizar: {msg}' },
        '更新失败，请检查网络连接': { tw: '更新失敗，請檢查網絡連線', en: 'Update failed. Check your network connection.', pt: 'Falha ao atualizar. Verifique a ligação à rede.' },
        '删除失败: {msg}': { tw: '刪除失敗：{msg}', en: 'Delete failed: {msg}', pt: 'Falha ao eliminar: {msg}' },
        '删除失败，请检查网络连接': { tw: '刪除失敗，請檢查網絡連線', en: 'Delete failed. Check your network connection.', pt: 'Falha ao eliminar. Verifique a ligação à rede.' },
        '正在查看 {name} 的健康详情... 这个功能正在开发中，即将推出！': { tw: '正在查看 {name} 的健康詳情... 這個功能正在開發中，即將推出！', en: "Viewing {name}'s health details...\n\nThis feature is under development and coming soon!", pt: 'A ver os detalhes de saúde de {name}...\n\nEsta funcionalidade está em desenvolvimento e chegará em breve!' },

        /* 新增貓咪表單 */
        '猫咪名字 *': { tw: '貓咪名字 *', en: 'Cat name *', pt: 'Nome do gato *' },
        '猫咪照片': { tw: '貓咪照片', en: 'Cat photo', pt: 'Foto do gato' },
        '点击上传猫咪照片': { tw: '點擊上傳貓咪照片', en: 'Click to upload a cat photo', pt: 'Clique para carregar uma foto do gato' },
        '选择性别': { tw: '選擇性別', en: 'Select gender', pt: 'Selecione o sexo' },
        '公': { tw: '公', en: 'Male', pt: 'Macho' },
        '母': { tw: '母', en: 'Female', pt: 'Fêmea' },
        '添加猫咪': { tw: '新增貓咪', en: 'Add Cat', pt: 'Adicionar gato' },
        '取消': { tw: '取消', en: 'Cancel', pt: 'Cancelar' },
        '输入猫咪名字': { tw: '輸入貓咪名字', en: 'Enter cat name', pt: 'Introduza o nome do gato' },
        '猫咪照片预览': { tw: '貓咪照片預覽', en: 'Cat photo preview', pt: 'Pré-visualização da foto do gato' },
        '图片预览': { tw: '圖片預覽', en: 'Image preview', pt: 'Pré-visualização da imagem' },
        '例如: 4.2': { tw: '例如：4.2', en: 'e.g. 4.2', pt: 'ex.: 4.2' },
        '例如: 英国短毛猫': { tw: '例如：英國短毛貓', en: 'e.g. British Shorthair', pt: 'ex.: British Shorthair' },
        '例如: 3岁': { tw: '例如：3歲', en: 'e.g. 3 years old', pt: 'ex.: 3 anos' },
        '例如: 4.2kg': { tw: '例如：4.2kg', en: 'e.g. 4.2 kg', pt: 'ex.: 4.2 kg' },
        '特殊需求、病史等信息': { tw: '特殊需求、病史等資訊', en: 'Special needs, medical history, etc.', pt: 'Necessidades especiais, histórico médico, etc.' },
        '特殊需求、病史等': { tw: '特殊需求、病史等', en: 'Special needs, medical history, etc.', pt: 'Necessidades especiais, histórico médico, etc.' },

        /* ==================== 健康詳情 ==================== */
        '查看猫咪的详细健康信息': { tw: '查看貓咪的詳細健康資訊', en: 'View detailed health information for your cat', pt: 'Ver informações detalhadas de saúde do gato' },
        '编辑健康信息': { tw: '編輯健康資訊', en: 'Edit Health Information', pt: 'Editar informações de saúde' },
        '体重 (kg)': { tw: '體重 (kg)', en: 'Weight (kg)', pt: 'Peso (kg)' },
        '保存健康信息': { tw: '儲存健康資訊', en: 'Save Health Information', pt: 'Guardar informações de saúde' },
        '返回猫咪档案': { tw: '返回貓咪檔案', en: 'Back to Cat Profiles', pt: 'Voltar aos perfis dos gatos' },

        /* ==================== 健康評估問卷 ==================== */
        '猫咪健康评估问卷': { tw: '貓咪健康評估問卷', en: 'Cat Health Assessment Questionnaire', pt: 'Questionário de avaliação de saúde do gato' },
        '请根据您猫咪的实际情况填写，获取个性化健康报告': { tw: '請根據您貓咪的實際情況填寫，獲取個人化健康報告', en: "Answer based on your cat's actual condition to get a personalised health report", pt: 'Responda com base na condição real do seu gato para obter um relatório de saúde personalizado' },
        '基本信息': { tw: '基本資訊', en: 'Basic Information', pt: 'Informações básicas' },
        '选择要评估的猫咪': { tw: '選擇要評估的貓咪', en: 'Select the cat to assess', pt: 'Selecione o gato a avaliar' },
        '请选择猫咪': { tw: '請選擇貓咪', en: 'Select a cat', pt: 'Selecione um gato' },
        '当前体重 (kg)': { tw: '當前體重 (kg)', en: 'Current weight (kg)', pt: 'Peso atual (kg)' },
        '饮食状况': { tw: '飲食狀況', en: 'Diet', pt: 'Alimentação' },
        '1. 猫咪的食欲如何？': { tw: '1. 貓咪的食慾如何？', en: "1. How is your cat's appetite?", pt: '1. Como está o apetite do seu gato?' },
        '非常好（主动讨食，吃完所有食物）': { tw: '非常好（主動討食，吃完所有食物）', en: 'Very good (actively asks for food and finishes everything)', pt: 'Muito bom (pede comida ativamente e come tudo)' },
        '良好（正常进食，偶尔剩食）': { tw: '良好（正常進食，偶爾剩食）', en: 'Good (eats normally, occasionally leaves food)', pt: 'Bom (come normalmente, às vezes deixa comida)' },
        '一般（食欲减退，经常剩食）': { tw: '一般（食慾減退，經常剩食）', en: 'Fair (reduced appetite, often leaves food)', pt: 'Razoável (apetite reduzido, deixa comida frequentemente)' },
        '差（几乎不进食）': { tw: '差（幾乎不進食）', en: 'Poor (hardly eats)', pt: 'Mau (quase não come)' },
        '2. 每日饮水量如何？': { tw: '2. 每日飲水量如何？', en: '2. How much water does your cat drink daily?', pt: '2. Quanta água bebe o seu gato por dia?' },
        '充足（主动频繁喝水）': { tw: '充足（主動頻繁喝水）', en: 'Plenty (drinks water actively and often)', pt: 'Suficiente (bebe água ativa e frequentemente)' },
        '正常（每天喝水数次）': { tw: '正常（每天喝水數次）', en: 'Normal (drinks several times a day)', pt: 'Normal (bebe várias vezes por dia)' },
        '偏少（很少主动喝水）': { tw: '偏少（很少主動喝水）', en: 'Low (rarely drinks water on its own)', pt: 'Reduzido (raramente bebe água por iniciativa própria)' },
        '极少（几乎不喝水）': { tw: '極少（幾乎不喝水）', en: 'Very low (almost never drinks)', pt: 'Muito reduzido (quase não bebe)' },
        '活动水平': { tw: '活動水平', en: 'Activity Level', pt: 'Nível de atividade' },
        '3. 猫咪的活动量如何？': { tw: '3. 貓咪的活動量如何？', en: '3. How active is your cat?', pt: '3. Quão ativo é o seu gato?' },
        '非常活跃（经常跑跳玩耍）': { tw: '非常活躍（經常跑跳玩耍）', en: 'Very active (runs, jumps and plays often)', pt: 'Muito ativo (corre, salta e brinca frequentemente)' },
        '活跃（每天有固定活动时间）': { tw: '活躍（每天有固定活動時間）', en: 'Active (has set play times every day)', pt: 'Ativo (tem momentos de atividade fixos todos os dias)' },
        '一般（偶尔活动，大部分时间休息）': { tw: '一般（偶爾活動，大部分時間休息）', en: 'Fair (occasionally active, rests most of the time)', pt: 'Razoável (atividade ocasional, descansa a maior parte do tempo)' },
        '懒散（几乎不活动）': { tw: '懶散（幾乎不活動）', en: 'Inactive (hardly moves)', pt: 'Inativo (quase não se move)' },
        '4. 玩耍时的精神状态？': { tw: '4. 玩耍時的精神狀態？', en: "4. How is your cat's energy when playing?", pt: '4. Como está a energia do seu gato quando brinca?' },
        '精力充沛（玩耍时间长）': { tw: '精力充沛（玩耍時間長）', en: 'Full of energy (plays for long periods)', pt: 'Cheio de energia (brinca durante longos períodos)' },
        '精神良好（有兴趣玩耍）': { tw: '精神良好（有興趣玩耍）', en: 'Good energy (interested in playing)', pt: 'Com boa energia (interessado em brincar)' },
        '精神一般（玩耍时间短）': { tw: '精神一般（玩耍時間短）', en: 'Moderate energy (short play sessions)', pt: 'Energia moderada (sessões de brincadeira curtas)' },
        '精神萎靡（对玩耍没兴趣）': { tw: '精神萎靡（對玩耍沒興趣）', en: 'Lethargic (not interested in playing)', pt: 'Letárgico (sem interesse em brincar)' },
        '排泄状况': { tw: '排泄狀況', en: 'Excretion', pt: 'Excreção' },
        '5. 排便情况如何？': { tw: '5. 排便情況如何？', en: "5. How are your cat's bowel movements?", pt: '5. Como estão as fezes do seu gato?' },
        '正常（成型，颜色正常）': { tw: '正常（成型，顏色正常）', en: 'Normal (well-formed, normal colour)', pt: 'Normal (bem formadas, cor normal)' },
        '基本正常（偶尔软便）': { tw: '基本正常（偶爾軟便）', en: 'Mostly normal (occasional soft stool)', pt: 'Quase normal (fezes moles ocasionais)' },
        '异常（经常软便或便秘）': { tw: '異常（經常軟便或便秘）', en: 'Abnormal (frequent soft stool or constipation)', pt: 'Anormal (fezes moles frequentes ou prisão de ventre)' },
        '严重异常（腹泻或便血）': { tw: '嚴重異常（腹瀉或便血）', en: 'Severely abnormal (diarrhoea or blood in stool)', pt: 'Muito anormal (diarreia ou sangue nas fezes)' },
        '6. 排尿情况如何？': { tw: '6. 排尿情況如何？', en: "6. How is your cat's urination?", pt: '6. Como está a micção do seu gato?' },
        '正常（频率颜色正常）': { tw: '正常（頻率顏色正常）', en: 'Normal (normal frequency and colour)', pt: 'Normal (frequência e cor normais)' },
        '基本正常（偶尔异常）': { tw: '基本正常（偶爾異常）', en: 'Mostly normal (occasional abnormalities)', pt: 'Quase normal (anomalias ocasionais)' },
        '异常（频率或颜色异常）': { tw: '異常（頻率或顏色異常）', en: 'Abnormal (unusual frequency or colour)', pt: 'Anormal (frequência ou cor anormais)' },
        '严重异常（尿血或排尿困难）': { tw: '嚴重異常（尿血或排尿困難）', en: 'Severely abnormal (blood in urine or difficulty urinating)', pt: 'Muito anormal (sangue na urina ou dificuldade em urinar)' },
        '行为表现': { tw: '行為表現', en: 'Behaviour', pt: 'Comportamento' },
        '7. 猫咪的睡眠质量？': { tw: '7. 貓咪的睡眠品質？', en: "7. How is your cat's sleep quality?", pt: '7. Como é a qualidade do sono do seu gato?' },
        '很好（睡眠安稳）': { tw: '很好（睡眠安穩）', en: 'Very good (sleeps soundly)', pt: 'Muito bom (dorme tranquilamente)' },
        '良好（偶尔惊醒）': { tw: '良好（偶爾驚醒）', en: 'Good (occasionally wakes up)', pt: 'Bom (acorda ocasionalmente)' },
        '一般（睡眠不安）': { tw: '一般（睡眠不安）', en: 'Fair (restless sleep)', pt: 'Razoável (sono inquieto)' },
        '差（失眠或过度睡眠）': { tw: '差（失眠或過度睡眠）', en: 'Poor (insomnia or oversleeping)', pt: 'Mau (insónia ou sono excessivo)' },
        '8. 与人的互动情况？': { tw: '8. 與人的互動情況？', en: '8. How does your cat interact with people?', pt: '8. Como é que o seu gato interage com as pessoas?' },
        '非常友好（主动亲近）': { tw: '非常友好（主動親近）', en: 'Very friendly (seeks affection)', pt: 'Muito amigável (procura afeto)' },
        '友好（回应互动）': { tw: '友好（回應互動）', en: 'Friendly (responds to interaction)', pt: 'Amigável (responde à interação)' },
        '一般（偶尔躲避）': { tw: '一般（偶爾躲避）', en: 'Fair (occasionally hides)', pt: 'Razoável (esconde-se ocasionalmente)' },
        '差（经常躲藏或攻击）': { tw: '差（經常躲藏或攻擊）', en: 'Poor (often hides or attacks)', pt: 'Mau (esconde-se ou ataca frequentemente)' },
        '生成健康报告': { tw: '生成健康報告', en: 'Generate Health Report', pt: 'Gerar relatório de saúde' },

        /* 評估結果 */
        '请选择要评估的猫咪': { tw: '請選擇要評估的貓咪', en: 'Please select a cat to assess', pt: 'Selecione um gato para avaliar' },
        '找不到该猫咪资料': { tw: '找不到該貓咪資料', en: 'Cat information not found', pt: 'Informação do gato não encontrada' },
        '{name}的健康评估报告': { tw: '{name} 的健康評估報告', en: "{name}'s Health Assessment Report", pt: 'Relatório de avaliação de saúde de {name}' },
        '整体健康指数': { tw: '整體健康指數', en: 'Overall Health Index', pt: 'Índice global de saúde' },
        '饮食状态': { tw: '飲食狀態', en: 'Diet Status', pt: 'Estado da alimentação' },
        '当前体重': { tw: '當前體重', en: 'Current Weight', pt: 'Peso atual' },
        '保存评估报告': { tw: '儲存評估報告', en: 'Save Assessment Report', pt: 'Guardar relatório de avaliação' },
        '返回主页': { tw: '返回主頁', en: 'Back to Home', pt: 'Voltar ao início' },
        '没有评估数据可保存': { tw: '沒有評估資料可儲存', en: 'No assessment data to save', pt: 'Não há dados de avaliação para guardar' },
        '✅ 健康评估报告保存成功！': { tw: '✅ 健康評估報告儲存成功！', en: '✅ Health assessment report saved!', pt: '✅ Relatório de avaliação de saúde guardado!' },
        '保存失败: {msg}': { tw: '儲存失敗：{msg}', en: 'Save failed: {msg}', pt: 'Falha ao guardar: {msg}' },
        '保存失败，请检查网络连接': { tw: '儲存失敗，請檢查網絡連線', en: 'Save failed. Check your network connection.', pt: 'Falha ao guardar. Verifique a ligação à rede.' },
        '需要关注': { tw: '需要關注', en: 'Needs Attention', pt: 'Requer atenção' },
        '建议尽快带猫咪去兽医处进行全面检查': { tw: '建議盡快帶貓咪去獸醫處進行全面檢查', en: 'Take your cat to the vet for a full check-up as soon as possible', pt: 'Leve o seu gato ao veterinário para um exame completo o quanto antes' },
        '饮食改善': { tw: '飲食改善', en: 'Improve Diet', pt: 'Melhorar a alimentação' },
        '尝试更换猫粮品牌，确保食物新鲜，定时定量喂食': { tw: '嘗試更換貓糧品牌，確保食物新鮮，定時定量餵食', en: 'Try a different cat food brand, keep food fresh, and feed at set times in set amounts', pt: 'Experimente outra marca de comida, mantenha a comida fresca e alimente a horas e em quantidades fixas' },
        '增加活动': { tw: '增加活動', en: 'Increase Activity', pt: 'Aumentar a atividade' },
        '每天安排15-30分钟的互动游戏，使用逗猫棒等玩具激发兴趣': { tw: '每天安排 15–30 分鐘的互動遊戲，使用逗貓棒等玩具激發興趣', en: 'Set aside 15–30 minutes of interactive play each day, using toys such as a cat wand', pt: 'Reserve 15–30 minutos de brincadeira interativa por dia, usando brinquedos como uma varinha para gatos' },
        '保持良好': { tw: '保持良好', en: 'Keep It Up', pt: 'Continue assim' },
        '猫咪状态很好，请继续保持当前的养护方式': { tw: '貓咪狀態很好，請繼續保持目前的養護方式', en: "Your cat is in good shape; keep up the current care routine", pt: 'O seu gato está bem; mantenha os cuidados atuais' },
        '小幅调整': { tw: '小幅調整', en: 'Minor Adjustment', pt: 'Pequeno ajuste' },
        '猫咪基本健康，建议关注饮食和活动量的改善': { tw: '貓咪基本健康，建議關注飲食和活動量的改善', en: "Your cat is basically healthy; consider improving diet and activity", pt: 'O seu gato está basicamente saudável; considere melhorar a alimentação e a atividade' },
        '饮水提醒': { tw: '飲水提醒', en: 'Hydration Reminder', pt: 'Lembrete de hidratação' },
        '确保猫咪有充足的清洁饮水，可以考虑使用流动饮水机': { tw: '確保貓咪有充足的清潔飲水，可以考慮使用流動飲水機', en: 'Make sure your cat has plenty of clean water; a pet water fountain may help', pt: 'Certifique-se de que o gato tem água limpa suficiente; uma fonte de água pode ajudar' },
        '环境丰富': { tw: '環境豐富', en: 'Enrich the Environment', pt: 'Enriquecer o ambiente' },
        '提供猫抓板、爬架等环境设施，满足猫咪的天性需求': { tw: '提供貓抓板、爬架等環境設施，滿足貓咪的天性需求', en: 'Provide scratching posts, cat trees and similar items to meet your cat\'s natural needs', pt: 'Forneça postes para arranhar, árvores para gatos e itens semelhantes para satisfazer as necessidades naturais do gato' },

        /* ==================== 附近醫院 ==================== */
        '附近宠物医院': { tw: '附近寵物醫院', en: 'Nearby Vet Hospitals', pt: 'Hospitais veterinários próximos' },
        '澳門境內寵物醫院地圖，點擊標記查看詳情': { cn: '澳门境内宠物医院地图，点击标记查看详情', tw: '澳門境內寵物醫院地圖，點擊標記查看詳情', en: 'Map of pet hospitals in Macau; tap a marker for details', pt: 'Mapa dos hospitais veterinários de Macau; toque num marcador para ver os detalhes' },
        '提示：': { tw: '提示：', en: 'Tip: ', pt: 'Dica: ' },
        '地圖功能需要騰訊地圖 API Key。申請地址：https://lbs.qq.com/dev/console/application/mine': { cn: '地图功能需要腾讯地图 API Key。申请地址：https://lbs.qq.com/dev/console/application/mine', tw: '地圖功能需要騰訊地圖 API Key。申請地址：https://lbs.qq.com/dev/console/application/mine', en: 'The map requires a Tencent Maps API key. Request one at: https://lbs.qq.com/dev/console/application/mine', pt: 'O mapa requer uma chave API do Tencent Maps. Solicite em: https://lbs.qq.com/dev/console/application/mine' },
        '醫院列表': { cn: '医院列表', tw: '醫院列表', en: 'Hospital List', pt: 'Lista de hospitais' },
        '點擊查看位置詳情': { cn: '点击查看位置详情', tw: '點擊查看位置詳情', en: 'Tap for location details', pt: 'Toque para ver os detalhes da localização' },
        '醫院名稱': { cn: '医院名称', tw: '醫院名稱', en: 'Hospital Name', pt: 'Nome do hospital' },
        '地址': { tw: '地址', en: 'Address', pt: 'Endereço' },
        '電話': { cn: '电话', tw: '電話', en: 'Phone', pt: 'Telefone' },
        '營業時間': { cn: '营业时间', tw: '營業時間', en: 'Opening Hours', pt: 'Horário de funcionamento' },
        '服務項目': { cn: '服务项目', tw: '服務項目', en: 'Services', pt: 'Serviços' },
        '開始導航': { cn: '开始导航', tw: '開始導航', en: 'Start Navigation', pt: 'Iniciar navegação' },
        '24小時急診熱線': { cn: '24小时急诊热线', tw: '24小時急診熱線', en: '24-Hour Emergency Hotline', pt: 'Linha de urgência 24 horas' },
        '如遇緊急情況，請立即撥打：': { cn: '如遇紧急情况，请立即拨打：', tw: '如遇緊急情況，請立即撥打：', en: 'In an emergency, call immediately: ', pt: 'Em caso de emergência, ligue imediatamente: ' },
        '（綠十字獸醫醫院）': { cn: '（绿十字兽医医院）', tw: '（綠十字獸醫醫院）', en: ' (Green Cross Veterinary Hospital)', pt: ' (Hospital Veterinário Cruz Verde)' },
        '緊急症狀：頻繁嘔吐、便血、精神萎靡、呼吸困難、抽搐、無法排尿': { cn: '紧急症状：频繁呕吐、便血、精神萎靡、呼吸困难、抽搐、无法排尿', tw: '緊急症狀：頻繁嘔吐、便血、精神萎靡、呼吸困難、抽搐、無法排尿', en: 'Emergency symptoms: frequent vomiting, blood in stool, lethargy, difficulty breathing, seizures, inability to urinate', pt: 'Sintomas de urgência: vómitos frequentes, sangue nas fezes, apatia, dificuldade em respirar, convulsões, incapacidade de urinar' },
        '24小時營業': { cn: '24小时营业', tw: '24小時營業', en: 'Open 24 hours', pt: 'Aberto 24 horas' },
        '急診': { cn: '急诊', tw: '急診', en: 'Emergency', pt: 'Urgência' },
        '全科': { tw: '全科', en: 'General Practice', pt: 'Clínica geral' },
        '手術': { cn: '手术', tw: '手術', en: 'Surgery', pt: 'Cirurgia' },
        '專科': { cn: '专科', tw: '專科', en: 'Specialities', pt: 'Especialidades' },
        '牙科': { tw: '牙科', en: 'Dentistry', pt: 'Odontologia' },
        '住院': { tw: '住院', en: 'Hospitalisation', pt: 'Internamento' },
        '皮膚科': { cn: '皮肤科', tw: '皮膚科', en: 'Dermatology', pt: 'Dermatologia' },
        '疫苗': { tw: '疫苗', en: 'Vaccination', pt: 'Vacinação' },
        '體檢': { cn: '体检', tw: '體檢', en: 'Health Check', pt: 'Check-up' },
        '絕育': { cn: '绝育', tw: '絕育', en: 'Neutering', pt: 'Esterilização' },
        '洗牙': { tw: '洗牙', en: 'Dental Cleaning', pt: 'Limpeza dentária' },
        '澳門寵物醫院列表': { cn: '澳门宠物医院列表', tw: '澳門寵物醫院列表', en: 'Macau Vet Hospital List', pt: 'Lista de hospitais veterinários de Macau' },
        '請設置騰訊地圖 API Key 以顯示地圖': { cn: '请设置腾讯地图 API Key 以显示地图', tw: '請設定騰訊地圖 API Key 以顯示地圖', en: 'Set a Tencent Maps API key to show the map', pt: 'Defina uma chave API do Tencent Maps para mostrar o mapa' },
        '最近的寵物醫院是：{name}，距離約 {distance} 公里': { cn: '最近的宠物医院是：{name}，距离约 {distance} 公里', tw: '最近的寵物醫院是：{name}，距離約 {distance} 公里', en: 'The nearest vet hospital is {name}, about {distance} km away', pt: 'O hospital veterinário mais próximo é {name}, a cerca de {distance} km' },
        '您的瀏覽器不支持地理定位': { cn: '您的浏览器不支持地理定位', tw: '您的瀏覽器不支持地理定位', en: 'Your browser does not support geolocation', pt: 'O seu navegador não suporta geolocalização' },
        '您當前位置不在澳門境內，顯示澳門中心位置': { cn: '您当前位置不在澳门境内，显示澳门中心位置', tw: '您當前位置不在澳門境內，顯示澳門中心位置', en: 'You are outside Macau; showing the centre of Macau', pt: 'Está fora de Macau; a mostrar o centro de Macau' },
        '無法獲取您的位置，請確保已允許定位權限': { cn: '无法获取您的位置，请确保已允许定位权限', tw: '無法獲取您的位置，請確保已允許定位權限', en: 'Unable to get your location. Make sure location permission is allowed.', pt: 'Não foi possível obter a sua localização. Certifique-se de que a permissão de localização está ativa.' },

        /* ==================== 設定 ==================== */
        '管理您的账号与应用偏好': { tw: '管理您的帳號與應用偏好', en: 'Manage your account and app preferences', pt: 'Gira a sua conta e preferências da aplicação' },
        '账号信息': { tw: '帳號資訊', en: 'Account Information', pt: 'Informações da conta' },
        '用户名': { tw: '使用者名稱', en: 'Username', pt: 'Nome de utilizador' },
        '邮箱': { tw: '電子郵件', en: 'Email', pt: 'E-mail' },
        '安全': { tw: '安全', en: 'Security', pt: 'Segurança' },
        '修改密码': { tw: '修改密碼', en: 'Change Password', pt: 'Alterar palavra-passe' },
        '修改密码功能即将上线': { tw: '修改密碼功能即將推出', en: 'Password change is coming soon', pt: 'A alteração de palavra-passe estará disponível em breve' },
        '数据': { tw: '資料', en: 'Data', pt: 'Dados' },
        '清除本地缓存': { tw: '清除本地緩存', en: 'Clear Local Cache', pt: 'Limpar cache local' },
        '確定要清除本地緩存嗎？這不會刪除您的賬號數據。': { cn: '确定要清除本地缓存吗？这不会删除您的账号数据。', tw: '確定要清除本地緩存嗎？這不會刪除您的賬號數據。', en: 'Clear the local cache? This will not delete your account data.', pt: 'Limpar a cache local? Isto não elimina os dados da sua conta.' },
        '✅ 本地缓存已清除': { tw: '✅ 本地緩存已清除', en: '✅ Local cache cleared', pt: '✅ Cache local limpa' },
        '关于': { tw: '關於', en: 'About', pt: 'Acerca' },
        '应用版本': { tw: '應用程式版本', en: 'App Version', pt: 'Versão da aplicação' },
        'AI 模型': { tw: 'AI 模型', en: 'AI Model', pt: 'Modelo de IA' },
        '后端服务': { tw: '後端服務', en: 'Backend Service', pt: 'Serviço backend' },

        /* ==================== 桌面寵物 / AI 健康助手 ==================== */
        'AI 健康助手': { tw: 'AI 健康助手', en: 'AI Health Assistant', pt: 'Assistente de saúde com IA' },
        '桌面宠物': { tw: '桌面寵物', en: 'Desktop pet', pt: 'Mascote no ecrã' },
        '宠物音效': { tw: '寵物音效', en: 'Pet sounds', pt: 'Sons do mascote' },
        'CatHealth 健康助手': { tw: 'CatHealth 健康助手', en: 'CatHealth Health Assistant', pt: 'Assistente de Saúde CatHealth' },
        '猫咪健康问答': { tw: '貓咪健康問答', en: 'Cat health Q&A', pt: 'Perguntas e respostas sobre saúde felina' },
        '打开 AI 健康助手': { tw: '開啟 AI 健康助手', en: 'Open AI health assistant', pt: 'Abrir o assistente de saúde com IA' },
        '清空对话': { tw: '清空對話', en: 'Clear conversation', pt: 'Limpar conversa' },
        '关闭': { tw: '關閉', en: 'Close', pt: 'Fechar' },
        '输入讯息...': { tw: '輸入訊息...', en: 'Type a message...', pt: 'Escreva uma mensagem...' },
        '输入讯息': { tw: '輸入訊息', en: 'Type a message', pt: 'Escreva uma mensagem' },
        '发送': { tw: '發送', en: 'Send', pt: 'Enviar' },
        '确定要清空所有消息吗？': { tw: '確定要清空所有訊息嗎？', en: 'Clear all messages?', pt: 'Limpar todas as mensagens?' },
        'AI 正在输入...': { tw: 'AI 正在輸入...', en: 'AI is typing...', pt: 'A IA está a escrever...' },
        '抱歉，我遇到了一些问题，请稍后重试。': { tw: '抱歉，我遇到了一些問題，請稍後重試。', en: 'Sorry, something went wrong. Please try again later.', pt: 'Desculpe, ocorreu um problema. Tente novamente mais tarde.' },
        '请求失败，请重试': { tw: '請求失敗，請重試', en: 'Request failed. Please try again.', pt: 'O pedido falhou. Tente novamente.' },
        '网络错误，请检查连接后重试。': { tw: '網絡錯誤，請檢查連線後重試。', en: 'Network error. Check your connection and try again.', pt: 'Erro de rede. Verifique a ligação e tente novamente.' },
        '请求超时，请稍后再试。': { tw: '請求逾時，請稍後再試。', en: 'Request timed out. Please try again later.', pt: 'O pedido expirou. Tente novamente mais tarde.' },
        '登录已过期，请重新登录。': { tw: '登入已逾時，請重新登入。', en: 'Your session has expired. Please sign in again.', pt: 'A sua sessão expirou. Inicie sessão novamente.' },
        '点我聊聊猫咪健康～': { tw: '點我聊聊貓咪健康～', en: 'Tap me to chat about cat health', pt: 'Toque em mim para falar sobre a saúde do gato' },
        '今天猫咪喝够水了吗？': { tw: '今天貓咪喝夠水了嗎？', en: 'Has your cat had enough water today?', pt: 'O seu gato bebeu água suficiente hoje?' },
        '猫咪的健康小助手在此！': { tw: '貓咪的健康小助手在此！', en: 'Your cat health helper is here!', pt: 'O seu assistente de saúde felina está aqui!' },
        '有健康问题想问我吗？': { tw: '有健康問題想問我嗎？', en: 'Any health questions for me?', pt: 'Tem alguma pergunta de saúde?' },
        '飞起来啦！': { tw: '飛起來啦！', en: 'Flying!', pt: 'A voar!' },
        '别甩我啦 QWQ': { tw: '別甩我啦 QWQ', en: 'Stop throwing me QWQ', pt: 'Não me atires QWQ' },
        '嗨！我是 CatHealth 健康小助手 🐋 有关猫咪饮食、饮水、排泄、体重或行为的问题，都可以问我喔！我的建议不能替代兽医诊断。': {
            tw: '嗨！我是 CatHealth 健康小助手 🐋 有關貓咪飲食、飲水、排泄、體重或行為的問題，都可以問我喔！我的建議不能替代獸醫診斷。',
            en: "Hi! I'm the CatHealth Assistant 🐋 Ask me anything about your cat's diet, water intake, litter box, weight or behaviour. My advice does not replace a vet's diagnosis.",
            pt: 'Olá! Sou o Assistente CatHealth 🐋 Pode perguntar-me sobre a alimentação, hidratação, excreção, peso ou comportamento do seu gato. Os meus conselhos não substituem o diagnóstico de um veterinário.'
        },

        /* ==================== 安裝提示 ==================== */
        '添加到桌面': { tw: '加到主畫面', en: 'Add to Home Screen', pt: 'Adicionar ao ecrã principal' },
        '将 CatHealth 添加到桌面，获得类似 App 的体验，快速访问猫咪健康管理功能': { tw: '將 CatHealth 加到主畫面，獲得類似 App 的體驗，快速存取貓咪健康管理功能', en: 'Add CatHealth to your home screen for an app-like experience and quick access to cat health management', pt: 'Adicione o CatHealth ao ecrã principal para uma experiência de aplicação e acesso rápido à gestão da saúde dos gatos' },
        '稍后再说': { tw: '稍後再說', en: 'Not now', pt: 'Agora não' },
        '✅ 已成功添加到桌面！': { tw: '✅ 已成功加到主畫面！', en: '✅ Added to home screen!', pt: '✅ Adicionado ao ecrã principal!' },
        '打開選單': { cn: '打开选单', tw: '開啟選單', en: 'Open menu', pt: 'Abrir menu' },

        /* ==================== 頁尾 / 意見反饋（原文為繁體） ==================== */
        '意見反饋': { cn: '意见反馈', tw: '意見反饋', en: 'Feedback', pt: 'Comentários' },
        '聯繫我們': { cn: '联系我们', tw: '聯繫我們', en: 'Contact Us', pt: 'Contacte-nos' },
        '© CatHealth Monitor · 守護每一隻貓咪的健康': { cn: '© CatHealth Monitor · 守护每一只猫咪的健康', tw: '© CatHealth Monitor · 守護每一隻貓咪的健康', en: '© CatHealth Monitor · Protecting the health of every cat', pt: '© CatHealth Monitor · A proteger a saúde de cada gato' },
        '反饋類型': { cn: '反馈类型', tw: '反饋類型', en: 'Feedback type', pt: 'Tipo de comentário' },
        '請選擇': { cn: '请选择', tw: '請選擇', en: 'Please select', pt: 'Selecione' },
        '功能異常 / Bug': { cn: '功能异常 / Bug', tw: '功能異常 / Bug', en: 'Bug', pt: 'Erro' },
        '功能建議': { cn: '功能建议', tw: '功能建議', en: 'Feature request', pt: 'Sugestão de funcionalidade' },
        '界面體驗': { cn: '界面体验', tw: '介面體驗', en: 'Interface', pt: 'Interface' },
        '其他': { tw: '其他', en: 'Other', pt: 'Outro' },
        '標題': { cn: '标题', tw: '標題', en: 'Subject', pt: 'Assunto' },
        '詳細描述': { cn: '详细描述', tw: '詳細描述', en: 'Details', pt: 'Descrição detalhada' },
        '聯繫郵箱（選填）': { cn: '联系邮箱（选填）', tw: '聯絡電郵（選填）', en: 'Contact email (optional)', pt: 'E-mail de contacto (opcional)' },
        '提交反饋': { cn: '提交反馈', tw: '提交反饋', en: 'Submit Feedback', pt: 'Enviar comentário' },
        '感謝您使用 CatHealth Monitor！': { cn: '感谢您使用 CatHealth Monitor！', tw: '感謝您使用 CatHealth Monitor！', en: 'Thank you for using CatHealth Monitor!', pt: 'Obrigado por utilizar o CatHealth Monitor!' },
        '如有任何問題或合作意向，歡迎通過以下方式聯繫我們：': { cn: '如有任何问题或合作意向，欢迎通过以下方式联系我们：', tw: '如有任何問題或合作意向，歡迎透過以下方式聯繫我們：', en: 'If you have any questions or partnership enquiries, contact us via:', pt: 'Se tiver alguma dúvida ou proposta de parceria, contacte-nos através de:' },
        '關閉': { cn: '关闭', tw: '關閉', en: 'Close', pt: 'Fechar' },
        '簡短描述您的反饋': { cn: '简短描述您的反馈', tw: '簡短描述您的反饋', en: 'Briefly describe your feedback', pt: 'Descreva brevemente o seu comentário' },
        '請詳細說明問題或建議，幫助我們改進...': { cn: '请详细说明问题或建议，帮助我们改进...', tw: '請詳細說明問題或建議，幫助我們改進...', en: 'Please describe the problem or suggestion in detail to help us improve...', pt: 'Descreva detalhadamente o problema ou sugestão para nos ajudar a melhorar...' },
        '感謝您的反饋！我們會認真參考您的建議。': { cn: '感谢您的反馈！我们会认真参考您的建议。', tw: '感謝您的反饋！我們會認真參考您的建議。', en: 'Thank you for your feedback! We will seriously consider your suggestions.', pt: 'Obrigado pelo seu comentário! Vamos considerar seriamente as suas sugestões.' },
        '感谢您的反馈！我们会认真参考您的建议。': { tw: '感謝您的反饋！我們會認真參考您的建議。', en: 'Thank you for your feedback! We will seriously consider your suggestions.', pt: 'Obrigado pelo seu comentário! Vamos considerar seriamente as suas sugestões.' },

        /* ==================== 登入 / 註冊頁 ==================== */
        '貓咪偵探社 - 猫咪健康监测': { cn: '猫咪侦探社 - 猫咪健康监测', tw: '貓咪偵探社 - 貓咪健康監測', en: 'Cat Detective - Cat Health Monitoring', pt: 'Detetive dos Gatos - Monitorização da saúde felina' },
        'AI 分析猫咪排泄物，实时监测健康风险': { tw: 'AI 分析貓咪排泄物，即時監測健康風險', en: 'AI analyses cat waste and monitors health risks in real time', pt: 'A IA analisa os dejetos dos gatos e monitoriza riscos de saúde em tempo real' },
        '用户登录': { tw: '使用者登入', en: 'Sign In', pt: 'Iniciar sessão' },
        '欢迎回到 CatHealth Monitor': { tw: '歡迎回到 CatHealth Monitor', en: 'Welcome back to CatHealth Monitor', pt: 'Bem-vindo de volta ao CatHealth Monitor' },
        '邮箱地址': { tw: '電子郵件地址', en: 'Email address', pt: 'Endereço de e-mail' },
        '密码': { tw: '密碼', en: 'Password', pt: 'Palavra-passe' },
        '记住帐号': { tw: '記住帳號', en: 'Remember account', pt: 'Memorizar conta' },
        '记住密码': { tw: '記住密碼', en: 'Remember password', pt: 'Memorizar palavra-passe' },
        '(本機)': { cn: '(本机)', tw: '(本機)', en: '(this device)', pt: '(este dispositivo)' },
        '密碼將保存在本機，僅建議在個人裝置使用': { cn: '密码将保存在本机，仅建议在个人装置使用', tw: '密碼將保存在本機，僅建議在個人裝置使用', en: 'The password will be stored on this device; recommended only on personal devices', pt: 'A palavra-passe será guardada neste dispositivo; recomendado apenas em dispositivos pessoais' },
        '忘记密码？': { tw: '忘記密碼？', en: 'Forgot password?', pt: 'Esqueceu-se da palavra-passe?' },
        '登录': { tw: '登入', en: 'Sign In', pt: 'Entrar' },
        '还没有账号？': { tw: '還沒有帳號？', en: 'No account yet? ', pt: 'Ainda não tem conta? ' },
        '立即注册': { tw: '立即註冊', en: 'Sign up now', pt: 'Registar agora' },
        '用户注册': { tw: '使用者註冊', en: 'Create Account', pt: 'Criar conta' },
        '创建您的 CatHealth Monitor 账号': { tw: '建立您的 CatHealth Monitor 帳號', en: 'Create your CatHealth Monitor account', pt: 'Crie a sua conta CatHealth Monitor' },
        '确认密码': { tw: '確認密碼', en: 'Confirm password', pt: 'Confirmar palavra-passe' },
        '我同意': { tw: '我同意', en: 'I agree to the', pt: 'Aceito os' },
        '服务条款': { tw: '服務條款', en: 'Terms of Service', pt: 'Termos de Serviço' },
        '和': { tw: '和', en: 'and', pt: 'e a' },
        '隐私政策': { tw: '隱私政策', en: 'Privacy Policy', pt: 'Política de Privacidade' },
        '注册账号': { tw: '註冊帳號', en: 'Create Account', pt: 'Criar conta' },
        '已有账号？': { tw: '已有帳號？', en: 'Already have an account? ', pt: 'Já tem conta? ' },
        '立即登录': { tw: '立即登入', en: 'Sign in now', pt: 'Iniciar sessão' },
        '使用YOLO模型自动分析猫咪排泄物特征，识别潜在健康风险': { tw: '使用 YOLO 模型自動分析貓咪排泄物特徵，識別潛在健康風險', en: 'Uses the YOLO model to analyse cat waste and identify potential health risks', pt: 'Utiliza o modelo YOLO para analisar os dejetos dos gatos e identificar potenciais riscos de saúde' },
        'GPS定位追踪': { tw: 'GPS 定位追蹤', en: 'GPS Tracking', pt: 'Localização GPS' },
        '实时追踪猫咪位置，设置安全区域，越界即时提醒': { tw: '即時追蹤貓咪位置，設定安全區域，越界即時提醒', en: "Track your cat's location in real time, set safe zones and get instant alerts when they leave", pt: 'Acompanhe a localização do gato em tempo real, defina zonas seguras e receba alertas quando sair' },
        '健康档案管理': { tw: '健康檔案管理', en: 'Health Records', pt: 'Registos de saúde' },
        '记录猫咪健康数据，生成健康报告，追踪长期趋势': { tw: '記錄貓咪健康資料，生成健康報告，追蹤長期趨勢', en: 'Record cat health data, generate health reports and track long-term trends', pt: 'Registe dados de saúde do gato, gere relatórios e acompanhe tendências a longo prazo' },
        '请输入您的邮箱': { tw: '請輸入您的電子郵件', en: 'Enter your email', pt: 'Introduza o seu e-mail' },
        '请输入您的密码': { tw: '請輸入您的密碼', en: 'Enter your password', pt: 'Introduza a sua palavra-passe' },
        '请输入用户名': { tw: '請輸入使用者名稱', en: 'Enter your username', pt: 'Introduza o seu nome de utilizador' },
        '请输入密码（至少8位）': { tw: '請輸入密碼（至少8位）', en: 'Enter a password (at least 8 characters)', pt: 'Introduza uma palavra-passe (pelo menos 8 caracteres)' },
        '请再次输入密码': { tw: '請再次輸入密碼', en: 'Enter the password again', pt: 'Introduza novamente a palavra-passe' },
        '登录中...': { tw: '登入中...', en: 'Signing in...', pt: 'A iniciar sessão...' },
        '注册中...': { tw: '註冊中...', en: 'Creating account...', pt: 'A criar conta...' },
        '登录失败': { tw: '登入失敗', en: 'Sign-in failed', pt: 'Falha ao iniciar sessão' },
        '注册失败': { tw: '註冊失敗', en: 'Registration failed', pt: 'Falha no registo' },
        '无法连接到服务器。可能是： 1. 服务器正在启动，请等待 30 秒后重试 2. 网络连接问题 请检查后端服务状态或稍后再试。': {
            tw: '無法連接到伺服器。可能是：\n1. 伺服器正在啟動，請等待 30 秒後重試\n2. 網絡連線問題\n\n請檢查後端服務狀態或稍後再試。',
            en: 'Unable to reach the server. Possible reasons:\n1. The server is starting; wait 30 seconds and try again\n2. Network connection issues\n\nCheck the backend status or try again later.',
            pt: 'Não foi possível contactar o servidor. Possíveis motivos:\n1. O servidor está a iniciar; aguarde 30 segundos e tente novamente\n2. Problemas de ligação à rede\n\nVerifique o estado do servidor ou tente mais tarde.'
        },
        '网络错误: {msg}': { tw: '網絡錯誤：{msg}', en: 'Network error: {msg}', pt: 'Erro de rede: {msg}' },
        '两次输入的密码不一致': { tw: '兩次輸入的密碼不一致', en: 'The passwords do not match', pt: 'As palavras-passe não coincidem' },
        '密码长度至少8位': { tw: '密碼長度至少8位', en: 'The password must be at least 8 characters', pt: 'A palavra-passe deve ter pelo menos 8 caracteres' },
        '请同意服务条款和隐私政策': { tw: '請同意服務條款和隱私政策', en: 'Please agree to the Terms of Service and Privacy Policy', pt: 'Aceite os Termos de Serviço e a Política de Privacidade' },
        '注册成功！欢迎使用 CatHealth Monitor': { tw: '註冊成功！歡迎使用 CatHealth Monitor', en: 'Registration successful! Welcome to CatHealth Monitor', pt: 'Registo concluído! Bem-vindo ao CatHealth Monitor' },

        /* ==================== 後端 AI 結果 ==================== */
        '便秘/干硬便便': { tw: '便秘／乾硬便便', en: 'Constipation / hard stool', pt: 'Prisão de ventre / fezes duras' },
        '拉稀': { tw: '拉稀', en: 'Diarrhoea', pt: 'Diarreia' },
        '正常': { tw: '正常', en: 'Normal', pt: 'Normal' },
        '未检测到排泄物': { tw: '未檢測到排泄物', en: 'No waste detected', pt: 'Não foram detetados dejetos' },
        '软便': { tw: '軟便', en: 'Soft stool', pt: 'Fezes moles' },
        '检测失败': { tw: '檢測失敗', en: 'Detection failed', pt: 'Falha na deteção' },
        '排便困难或粪便干硬，建议增加水分摄入并调整饮食。': { tw: '排便困難或糞便乾硬，建議增加水分攝取並調整飲食。', en: 'Difficulty defecating or hard stools. Increase water intake and adjust the diet.', pt: 'Dificuldade em defecar ou fezes duras. Aumente a ingestão de água e ajuste a dieta.' },
        '严重肠道问题，建议尽快就医检查。': { tw: '嚴重腸道問題，建議儘快就醫檢查。', en: 'Serious intestinal problem. Seek veterinary care as soon as possible.', pt: 'Problema intestinal grave. Consulte um veterinário o mais rápido possível.' },
        '猫咪排泄物形态正常，建议保持当前饮食和生活方式。': { tw: '貓咪排泄物形態正常，建議保持目前飲食和生活方式。', en: "Your cat's waste looks normal. Keep the current diet and lifestyle.", pt: 'Os dejetos do seu gato parecem normais. Mantenha a dieta e o estilo de vida atuais.' },
        '图片中未识别到猫咪排泄物，请上传清晰的猫咪排泄物照片。': { tw: '圖片中未識別到貓咪排泄物，請上傳清晰的貓咪排泄物照片。', en: 'No cat waste was recognised in the image. Please upload a clear photo.', pt: 'Não foram reconhecidos dejetos de gato na imagem. Carregue uma foto nítida.' },
        '轻度肠道不适，建议观察饮食并适当调整。': { tw: '輕度腸道不適，建議觀察飲食並適當調整。', en: 'Mild intestinal discomfort. Monitor the diet and adjust as needed.', pt: 'Desconforto intestinal ligeiro. Vigie a dieta e ajuste conforme necessário.' },
        '请稍后重试或联系管理员': { tw: '請稍後重試或聯絡管理員', en: 'Please try again later or contact the administrator', pt: 'Tente novamente mais tarde ou contacte o administrador' },
        '请上传更清晰的猫咪排泄物照片，确保粪便位于画面中央、光线充足': { tw: '請上傳更清晰的貓咪排泄物照片，確保糞便位於畫面中央、光線充足', en: "Please upload a clearer photo of your cat's waste, with the stool centred and well lit", pt: 'Carregue uma foto mais nítida dos dejetos do gato, com as fezes centradas e bem iluminadas' },
        'YOLOv11未在图像中检测到猫咪排泄物，请上传清晰的猫咪排泄物照片': { tw: 'YOLOv11 未在圖像中檢測到貓咪排泄物，請上傳清晰的貓咪排泄物照片', en: 'YOLOv11 did not detect cat waste in the image. Please upload a clear photo.', pt: 'O YOLOv11 não detetou dejetos de gato na imagem. Carregue uma foto nítida.' },
        '检测到: {name}': { tw: '檢測到：{name}', en: 'Detected: {name}', pt: 'Detetado: {name}' },
        'YOLOv11检测 - {name}': { tw: 'YOLOv11 檢測 - {name}', en: 'YOLOv11 detection - {name}', pt: 'Deteção YOLOv11 - {name}' },
        'AI检测到{name}，但置信度较低，建议上传更清晰的图片': { tw: 'AI 檢測到{name}，但置信度較低，建議上傳更清晰的圖片', en: 'AI detected {name}, but confidence is low. Upload a clearer image.', pt: 'A IA detetou {name}, mas a confiança é baixa. Carregue uma imagem mais nítida.' },
        'AI检测到疑似目标，但置信度仅{conf}，不足以给出准确判断': { tw: 'AI 檢測到疑似目標，但置信度僅 {conf}，不足以給出準確判斷', en: 'AI detected a possible target, but confidence is only {conf}, which is not enough for an accurate judgement', pt: 'A IA detetou um possível alvo, mas a confiança é apenas {conf}, o que não permite uma avaliação precisa' },
        'AI检测到{name}，置信度{conf}。建议上传更清晰的猫咪排泄物照片以获得更准确的结果。': { tw: 'AI 檢測到{name}，置信度 {conf}。建議上傳更清晰的貓咪排泄物照片以獲得準確結果。', en: 'AI detected {name} with {conf} confidence. Upload a clearer photo of the waste for a more accurate result.', pt: 'A IA detetou {name} com uma confiança de {conf}. Carregue uma foto mais nítida dos dejetos para obter um resultado mais preciso.' },
        '{advice}（建议上传更清晰的图片以确认）': { tw: '{advice}（建議上傳更清晰的圖片以確認）', en: '{advice} (upload a clearer image to confirm)', pt: '{advice} (carregue uma imagem mais nítida para confirmar)' },
        '检测出错: {msg}': { tw: '檢測出錯：{msg}', en: 'Detection error: {msg}', pt: 'Erro na deteção: {msg}' },
        'AI分析结果为{name}，风险指数{risk}%。{advice}': { tw: 'AI 分析結果為{name}，風險指數 {risk}%。{advice}', en: 'AI analysis result: {name}, risk index {risk}%. {advice}', pt: 'Resultado da análise de IA: {name}, índice de risco {risk}%. {advice}' },

        /* ==================== 後端 API 錯誤訊息（英文原文） ==================== */
        'Invalid email or password': { cn: '邮箱或密码错误', tw: '電郵或密碼錯誤', en: 'Invalid email or password', pt: 'E-mail ou palavra-passe inválidos' },
        'Email already exists': { cn: '该邮箱已被注册', tw: '此電郵已被註冊', en: 'Email already exists', pt: 'Este e-mail já está registado' },
        'Password must be at least 8 characters': { cn: '密码长度至少8位', tw: '密碼長度至少8位', en: 'Password must be at least 8 characters', pt: 'A palavra-passe deve ter pelo menos 8 caracteres' },
        'Email, password and name are required': { cn: '请填写邮箱、密码和用户名', tw: '請填寫電郵、密碼和使用者名稱', en: 'Email, password and name are required', pt: 'E-mail, palavra-passe e nome são obrigatórios' },
        'Email and password are required': { cn: '请填写邮箱和密码', tw: '請填寫電郵和密碼', en: 'Email and password are required', pt: 'E-mail e palavra-passe são obrigatórios' },
        'No data provided': { cn: '未提供数据', tw: '未提供資料', en: 'No data provided', pt: 'Nenhum dado fornecido' },
        'Cat name is required': { cn: '请填写猫咪名字', tw: '請填寫貓咪名字', en: 'Cat name is required', pt: 'O nome do gato é obrigatório' },
        'Cat not found': { cn: '找不到猫咪', tw: '找不到貓咪', en: 'Cat not found', pt: 'Gato não encontrado' },
        'Cat not found or no permission': { cn: '找不到猫咪或没有权限', tw: '找不到貓咪或沒有權限', en: 'Cat not found or no permission', pt: 'Gato não encontrado ou sem permissão' },
        'Token has expired': { cn: '登录已过期，请重新登录', tw: '登入已逾時，請重新登入', en: 'Token has expired', pt: 'A sessão expirou; inicie sessão novamente' },
        'Token is invalid': { cn: '登录凭证无效，请重新登录', tw: '登入憑證無效，請重新登入', en: 'Token is invalid', pt: 'Credenciais de sessão inválidas; inicie sessão novamente' },
        'Token is missing': { cn: '缺少登录凭证', tw: '缺少登入憑證', en: 'Token is missing', pt: 'Credenciais de sessão em falta' },
        'Token format invalid': { cn: '登录凭证格式无效', tw: '登入憑證格式無效', en: 'Token format invalid', pt: 'Formato de credenciais inválido' },
        'User not found': { cn: '找不到用户', tw: '找不到使用者', en: 'User not found', pt: 'Utilizador não encontrado' },
        'Internal server error, please try again later': { cn: '服务器内部错误，请稍后再试', tw: '伺服器內部錯誤，請稍後再試', en: 'Internal server error, please try again later', pt: 'Erro interno do servidor; tente novamente mais tarde' },
        'No image data': { cn: '没有图片数据', tw: '沒有圖片資料', en: 'No image data', pt: 'Sem dados da imagem' },
        'Decode failed': { cn: '图片解码失败', tw: '圖片解碼失敗', en: 'Decode failed', pt: 'Falha ao descodificar a imagem' },
        'Invalid request': { cn: '请求无效', tw: '請求無效', en: 'Invalid request', pt: 'Pedido inválido' },
        'Conversation is too long': { cn: '对话内容过长，请清空后重试。', tw: '對話內容過長，請清空後重試。', en: 'Conversation is too long. Please clear it and try again.', pt: 'A conversa é demasiado longa. Limpe-a e tente novamente.' }
    };

    /* ==================== 核心 ==================== */

    function normalize(value) {
        return String(value).replace(/\s+/g, ' ').trim();
    }

    function safeGetStorage(key) {
        try { return global.localStorage.getItem(key); } catch (e) { return null; }
    }

    function safeSetStorage(key, value) {
        try { global.localStorage.setItem(key, value); } catch (e) { /* ignore */ }
    }

    function getLanguage() {
        var saved = safeGetStorage(STORAGE_KEY);
        return SUPPORTED.indexOf(saved) !== -1 ? saved : DEFAULT_LANG;
    }

    function setLanguage(code) {
        if (SUPPORTED.indexOf(code) === -1) return false;
        safeSetStorage(STORAGE_KEY, code);
        document.documentElement.lang = HTML_LANG[code] || 'zh-CN';
        return true;
    }

    function pick(entry, lang, fallback) {
        if (!entry) return fallback;
        var value;
        if (lang === 'zh-TW') value = entry.tw;
        else if (lang === 'en') value = entry.en;
        else if (lang === 'pt') value = entry.pt;
        else value = entry.cn;
        return value !== undefined && value !== null && value !== '' ? value : fallback;
    }

    /** 翻譯一般文字（保留前後空白）。 */
    function translate(value) {
        var text = String(value);
        var leading = text.match(/^\s*/)[0];
        var trailing = text.match(/\s*$/)[0];
        var core = text.slice(leading.length, text.length - trailing.length);
        if (!core) return text;
        var entry = DICT[normalize(core)];
        if (!entry) return text;
        return leading + pick(entry, getLanguage(), core) + trailing;
    }

    /** 翻譯屬性值。 */
    function translateAttribute(value) {
        if (value === null || value === undefined) return value;
        var text = String(value);
        var entry = DICT[normalize(text)];
        return entry ? pick(entry, getLanguage(), text) : value;
    }

    /** 以字串模板翻譯：t('歡迎回來，{name}！', { name: 'Mimi' }) */
    function t(text, params) {
        var source = String(text);
        var entry = DICT[normalize(source)];
        var output = entry ? pick(entry, getLanguage(), source) : source;
        if (params) {
            output = output.replace(/\{(\w+)\}/g, function (match, key) {
                return params[key] !== undefined && params[key] !== null ? params[key] : '';
            });
        }
        return output;
    }

    /** 翻譯後端回傳的已知 AI 分析文字（類別、建議、特徵描述）。 */
    function backend(value) {
        if (value === null || value === undefined) return '';
        var text = String(value);
        if (getLanguage() === 'zh-CN') return text;

        var entry = DICT[normalize(text)];
        if (entry) return pick(entry, getLanguage(), text);

        var m;
        if ((m = text.match(/^检测到:\s*(.+)$/))) {
            return t('检测到: {name}', { name: backend(m[1]) });
        }
        if ((m = text.match(/^YOLOv11检测\s*-\s*(.+)$/))) {
            return t('YOLOv11检测 - {name}', { name: backend(m[1]) });
        }
        if ((m = text.match(/^AI检测到(.+?)，但置信度较低，建议上传更清晰的图片$/))) {
            return t('AI检测到{name}，但置信度较低，建议上传更清晰的图片', { name: backend(m[1]) });
        }
        if ((m = text.match(/^AI检测到疑似目标，但置信度仅(.+?)，不足以给出准确判断$/))) {
            return t('AI检测到疑似目标，但置信度仅{conf}，不足以给出准确判断', { conf: m[1] });
        }
        if ((m = text.match(/^AI检测到(.+?)，置信度(.+?)。建议上传更清晰的猫咪排泄物照片以获得更准确的结果。$/))) {
            return t('AI检测到{name}，置信度{conf}。建议上传更清晰的猫咪排泄物照片以获得更准确的结果。', { name: backend(m[1]), conf: m[2] });
        }
        if ((m = text.match(/^(.+?)\s*\(建议上传更清晰的图片以确认\)$/))) {
            return t('{advice}（建议上传更清晰的图片以确认）', { advice: backend(m[1]) });
        }
        if ((m = text.match(/^(.+?)\s*\((\d+(?:\.\d+)?%)\)$/))) {
            return backend(m[1]) + ' (' + m[2] + ')';
        }
        if ((m = text.match(/^检测出错:\s*(.+)$/))) {
            return t('检测出错: {msg}', { msg: m[1] });
        }
        if ((m = text.match(/^AI分析结果为(.+?)，风险指数(.+?)。(.+)$/))) {
            return t('AI分析结果为{name}，风险指数{risk}%。{advice}', {
                name: backend(m[1]),
                risk: m[2].replace(/%$/, ''),
                advice: backend(m[3])
            });
        }
        return text;
    }

    /* ==================== DOM 翻譯 ==================== */

    var SKIP_TAGS = { SCRIPT: true, STYLE: true, NOSCRIPT: true, CODE: true, PRE: true };

    function isSkipped(el) {
        return !el || el.nodeType !== 1 || SKIP_TAGS[el.tagName] === true || el.hasAttribute('data-i18n-skip');
    }

    function translateTextNode(node) {
        if (!node || node.nodeType !== 3) return;
        var parent = node.parentNode;
        if (parent && parent.nodeType === 1 && isSkipped(parent)) return;
        var output = translate(node.nodeValue);
        if (output !== node.nodeValue) node.nodeValue = output;
    }

    function translateAttributes(el) {
        if (!el || el.nodeType !== 1 || isSkipped(el)) return;
        var names = ['placeholder', 'title', 'aria-label', 'alt'];
        for (var i = 0; i < names.length; i++) {
            var name = names[i];
            if (!el.hasAttribute(name)) continue;
            var current = el.getAttribute(name);
            var output = translateAttribute(current);
            if (output !== current) el.setAttribute(name, output);
        }
    }

    function translateTree(root) {
        if (!root) return;
        if (root.nodeType === 3) { translateTextNode(root); return; }
        if (root.nodeType === 11) { // DocumentFragment
            for (var i = 0; i < root.childNodes.length; i++) translateTree(root.childNodes[i]);
            return;
        }
        if (root.nodeType !== 1 || isSkipped(root)) return;
        translateAttributes(root);
        var children = root.childNodes;
        for (var j = 0; j < children.length; j++) translateTree(children[j]);
    }

    var observer = null;

    function startObserver() {
        if (observer || typeof global.MutationObserver === 'undefined') return;
        observer = new global.MutationObserver(function (mutations) {
            for (var i = 0; i < mutations.length; i++) {
                var mutation = mutations[i];
                if (mutation.type === 'characterData') {
                    translateTextNode(mutation.target);
                } else if (mutation.type === 'childList') {
                    for (var j = 0; j < mutation.addedNodes.length; j++) {
                        translateTree(mutation.addedNodes[j]);
                    }
                } else if (mutation.type === 'attributes' && mutation.attributeName) {
                    var el = mutation.target;
                    if (el && el.nodeType === 1 && !isSkipped(el)) {
                        var current = el.getAttribute(mutation.attributeName);
                        var output = translateAttribute(current);
                        if (output !== current) el.setAttribute(mutation.attributeName, output);
                    }
                }
            }
        });
        observer.observe(document.documentElement, {
            childList: true,
            subtree: true,
            characterData: true,
            attributes: true,
            attributeFilter: ['placeholder', 'title', 'aria-label', 'alt']
        });
    }

    function installDialogHooks() {
        if (global.__cathealthI18nDialogHooks) return;
        global.__cathealthI18nDialogHooks = true;

        var nativeAlert = global.alert;
        var nativeConfirm = global.confirm;

        if (typeof nativeAlert === 'function') {
            global.alert = function (message) {
                return nativeAlert.call(global, translate(message));
            };
        }
        if (typeof nativeConfirm === 'function') {
            global.confirm = function (message) {
                return nativeConfirm.call(global, translate(message));
            };
        }
    }

    function apply() {
        translateTree(document.documentElement);
    }

    function boot() {
        document.documentElement.lang = HTML_LANG[getLanguage()] || 'zh-CN';
        installDialogHooks();
        apply();
        startObserver();
        document.dispatchEvent(new global.CustomEvent('cathealth:i18n-ready', {
            detail: { language: getLanguage() }
        }));
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', boot, { once: true });
    } else {
        boot();
    }

    global.I18n = {
        languages: SUPPORTED.slice(),
        storageKey: STORAGE_KEY,
        getLanguage: getLanguage,
        setLanguage: setLanguage,
        t: t,
        backend: backend,
        translate: translate,
        apply: apply
    };

})(window);
