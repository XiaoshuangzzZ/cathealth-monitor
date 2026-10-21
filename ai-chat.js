/*!
 * CatHealth Monitor - AI 健康助手
 * 移植自微信小程序的 AI 聊天頁，改為 CatHealth 的貓咪健康助理。
 */
(function (global) {
    'use strict';

    var WELCOME_KEY = '嗨！我是 CatHealth 健康小助手 🐋 有关猫咪饮食、饮水、排泄、体重或行为的问题，都可以问我喔！我的建议不能替代兽医诊断。';
    var MAX_MESSAGES = 12;

    var overlay = null;
    var listEl = null;
    var formEl = null;
    var inputEl = null;
    var sendBtn = null;
    var closeBtn = null;
    var clearBtn = null;
    var typingEl = null;

    var history = [];
    var isSending = false;
    var isOpen = false;
    var initialized = false;
    var abortController = null;

    function tr(text, params) {
        try {
            return global.I18n ? global.I18n.t(text, params) : text;
        } catch (e) {
            return text;
        }
    }

    function localizeKnown(text) {
        try {
            return global.I18n ? global.I18n.translate(text) : text;
        } catch (e) {
            return text;
        }
    }

    function escapeHtml(value) {
        return String(value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function renderMarkdown(value) {
        var codeBlocks = [];
        var text = escapeHtml(value);

        text = text.replace(/```([\s\S]*?)```/g, function (_, code) {
            codeBlocks.push(code.replace(/^\n+|\n+$/g, ''));
            return '@@CODEBLOCK' + (codeBlocks.length - 1) + '@@';
        });

        text = text.replace(/`([^`]+)`/g, '<code>$1</code>');
        text = text.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
        text = text.replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>');
        text = text.replace(/\n/g, '<br>');

        text = text.replace(/@@CODEBLOCK(\d+)@@/g, function (_, index) {
            return '<pre><code>' + codeBlocks[Number(index)] + '</code></pre>';
        });

        return text;
    }

    function currentTime() {
        var now = new Date();
        return String(now.getHours()).padStart(2, '0') + ':' + String(now.getMinutes()).padStart(2, '0');
    }

    function apiBase() {
        try {
            if (typeof global.getApiBaseUrl === 'function') return global.getApiBaseUrl();
        } catch (e) { /* ignore */ }
        return global.location.origin || '';
    }

    function scrollToBottom(force) {
        if (!listEl) return;
        var run = function () {
            listEl.scrollTop = listEl.scrollHeight;
        };
        if (force) run();
        global.requestAnimationFrame(function () {
            run();
            global.setTimeout(run, 80);
        });
    }

    function removeTyping() {
        if (typingEl && typingEl.parentNode) typingEl.parentNode.removeChild(typingEl);
        typingEl = null;
    }

    function showTyping() {
        if (!listEl || typingEl) return;
        typingEl = document.createElement('div');
        typingEl.className = 'ai-chat-msg ai-chat-msg-ai ai-chat-msg-typing';
        typingEl.setAttribute('aria-label', tr('AI 正在输入...'));
        typingEl.innerHTML =
            '<img class="ai-chat-msg-avatar" src="pet/Dsleep-avatar.png" alt="">' +
            '<div class="ai-chat-msg-body">' +
                '<div class="ai-chat-bubble ai-chat-typing-bubble">' +
                    '<span class="ai-chat-dot"></span><span class="ai-chat-dot"></span><span class="ai-chat-dot"></span>' +
                '</div>' +
            '</div>';
        listEl.appendChild(typingEl);
        scrollToBottom(true);
    }

    function createMessageElement(role, content, options) {
        options = options || {};
        var wrap = document.createElement('div');
        wrap.className = 'ai-chat-msg ' + (role === 'user' ? 'ai-chat-msg-user' : 'ai-chat-msg-ai');

        if (role !== 'user') {
            var avatar = document.createElement('img');
            avatar.className = 'ai-chat-msg-avatar';
            avatar.src = 'pet/Dsleep-avatar.png';
            avatar.alt = '';
            wrap.appendChild(avatar);
        }

        var body = document.createElement('div');
        body.className = 'ai-chat-msg-body';

        if (!options.hideTime) {
            var time = document.createElement('span');
            time.className = 'ai-chat-time';
            time.textContent = currentTime();
            body.appendChild(time);
        }

        var bubble = document.createElement('div');
        bubble.className = 'ai-chat-bubble' + (options.isError ? ' error' : '');

        if (role === 'user' || options.plainText) {
            bubble.textContent = content;
        } else {
            bubble.innerHTML = renderMarkdown(content);
        }

        body.appendChild(bubble);
        wrap.appendChild(body);

        if (role === 'user') {
            var userAvatar = document.createElement('div');
            userAvatar.className = 'ai-chat-user-avatar';
            userAvatar.innerHTML = '<i class="fas fa-user"></i>';
            wrap.appendChild(userAvatar);
        }

        return wrap;
    }

    function appendMessage(role, content, options) {
        if (!listEl) return;
        listEl.appendChild(createMessageElement(role, content, options));
        scrollToBottom();
    }

    function renderWelcome() {
        if (!listEl) return;
        listEl.innerHTML = '';
        var welcome = createMessageElement('assistant', tr(WELCOME_KEY), { hideTime: true, plainText: true });
        welcome.classList.add('ai-chat-welcome');
        listEl.appendChild(welcome);
    }

    function resetConversation() {
        history = [];
        removeTyping();
        renderWelcome();
        isSending = false;
        if (abortController) {
            try { abortController.abort(); } catch (e) { /* ignore */ }
            abortController = null;
        }
        updateSendButton();
    }

    function updateSendButton() {
        if (!sendBtn || !inputEl) return;
        var hasText = inputEl.value.trim().length > 0;
        sendBtn.disabled = !hasText || isSending;
        sendBtn.classList.toggle('active', hasText && !isSending);
    }

    function resizeInput() {
        if (!inputEl) return;
        inputEl.style.height = 'auto';
        inputEl.style.height = Math.min(inputEl.scrollHeight, 120) + 'px';
    }

    async function sendMessage() {
        if (!inputEl || isSending) return;
        var content = inputEl.value.trim();
        if (!content) return;

        inputEl.value = '';
        resizeInput();
        updateSendButton();

        appendMessage('user', content);
        history.push({ role: 'user', content: content });
        if (history.length > MAX_MESSAGES) {
            history = history.slice(history.length - MAX_MESSAGES);
        }

        isSending = true;
        showTyping();
        updateSendButton();

        var token = '';
        try { token = global.localStorage.getItem('cathealth_token') || ''; } catch (e) { /* ignore */ }

        abortController = new AbortController();
        var timeoutId = global.setTimeout(function () {
            try { abortController.abort(); } catch (e) { /* ignore */ }
        }, 60000);

        try {
            var response = await fetch(apiBase() + '/api/ai/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + token
                },
                body: JSON.stringify({
                    messages: history.slice(),
                    language: global.I18n ? global.I18n.getLanguage() : 'zh-CN'
                }),
                signal: abortController.signal
            });

            var data = null;
            try { data = await response.json(); } catch (e) { data = null; }
            global.clearTimeout(timeoutId);
            removeTyping();

            if (response.status === 401) {
                appendMessage('assistant', tr('登录已过期，请重新登录。'), { isError: true, plainText: true });
            } else if (!response.ok) {
                var serverError = data && data.error ? localizeKnown(data.error) : tr('请求失败，请重试');
                appendMessage('assistant', serverError, { isError: true, plainText: true });
            } else if (!data || !data.success || !data.data) {
                var apiError = data && data.error ? localizeKnown(data.error) : tr('抱歉，我遇到了一些问题，请稍后重试。');
                appendMessage('assistant', apiError, { isError: true, plainText: true });
            } else {
                appendMessage('assistant', String(data.data));
                history.push({ role: 'assistant', content: String(data.data) });
                if (history.length > MAX_MESSAGES) {
                    history = history.slice(history.length - MAX_MESSAGES);
                }
            }
        } catch (error) {
            global.clearTimeout(timeoutId);
            removeTyping();
            var message = tr('网络错误，请检查连接后重试。');
            if (error && error.name === 'AbortError') {
                message = tr('请求超时，请稍后再试。');
            }
            appendMessage('assistant', message, { isError: true, plainText: true });
        } finally {
            abortController = null;
            isSending = false;
            updateSendButton();
            scrollToBottom();
        }
    }

    function open() {
        init();
        if (!overlay) return;
        isOpen = true;
        overlay.classList.add('open');
        overlay.setAttribute('aria-hidden', 'false');
        document.body.classList.add('ai-chat-open');
        scrollToBottom(true);
        if (global.innerWidth > 768) {
            global.setTimeout(function () {
                if (inputEl) inputEl.focus();
            }, 180);
        }
    }

    function close() {
        if (!overlay) return;
        isOpen = false;
        overlay.classList.remove('open');
        overlay.setAttribute('aria-hidden', 'true');
        document.body.classList.remove('ai-chat-open');
        if (inputEl) inputEl.blur();
    }

    function bindEvents() {
        formEl.addEventListener('submit', function (event) {
            event.preventDefault();
            sendMessage();
        });

        inputEl.addEventListener('input', function () {
            resizeInput();
            updateSendButton();
        });

        inputEl.addEventListener('keydown', function (event) {
            if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
                event.preventDefault();
                sendMessage();
            }
        });

        closeBtn.addEventListener('click', close);
        clearBtn.addEventListener('click', function () {
            if (isSending) return;
            if (history.length === 0) return;
            if (global.confirm(tr('确定要清空所有消息吗？'))) {
                resetConversation();
            }
        });

        overlay.addEventListener('click', function (event) {
            if (event.target === overlay) close();
        });

        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape' && isOpen) close();
        });
    }

    function init() {
        if (initialized) return;
        initialized = true;

        overlay = document.getElementById('ai-chat-overlay');
        listEl = document.getElementById('ai-chat-messages');
        formEl = document.getElementById('ai-chat-form');
        inputEl = document.getElementById('ai-chat-input');
        sendBtn = document.getElementById('ai-chat-send');
        closeBtn = document.getElementById('ai-chat-close');
        clearBtn = document.getElementById('ai-chat-clear');

        if (!overlay || !listEl || !formEl || !inputEl || !sendBtn || !closeBtn || !clearBtn) {
            return;
        }

        renderWelcome();
        bindEvents();
        updateSendButton();
    }

    global.openAIChat = function (event) {
        if (event && typeof event.preventDefault === 'function') event.preventDefault();
        if (event && typeof event.stopPropagation === 'function') event.stopPropagation();
        open();
    };

    global.CatHealthChat = {
        open: open,
        close: close,
        reset: resetConversation,
        isOpen: function () { return isOpen; }
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init, { once: true });
    } else {
        init();
    }

})(window);
