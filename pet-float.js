/*!
 * CatHealth Monitor - 桌面寵物（鯨魚）
 * 移植自微信小程序的 pet-float 組件：
 * 拖曳、慣性滑動、邊界回彈、翻轉、氣泡提示與 D1-D3 音效。
 */
(function (global) {
    'use strict';

    var STORAGE_ENABLED = 'cathealth_pet_enabled';
    var STORAGE_SOUND = 'cathealth_pet_sound';
    var MARGIN = 30;
    var TIPS = [
        '点我聊聊猫咪健康～',
        '今天猫咪喝够水了吗？',
        '猫咪的健康小助手在此！',
        '有健康问题想问我吗？'
    ];
    var THROW_TEXTS = [
        '飞起来啦！',
        '别甩我啦 QWQ'
    ];

    var el = null;
    var img = null;
    var bubble = null;
    var bubbleText = null;
    var initialized = false;

    var x = 0;
    var y = 0;
    var scale = 1;
    var rotation = 0;
    var isDragging = false;
    var isAnimating = false;

    var vx = 0;
    var vy = 0;
    var rafId = null;
    var lastFrame = 0;
    var lastPositions = [];
    var touchStartX = 0;
    var touchStartY = 0;
    var touchStartTime = 0;
    var hasMoved = false;
    var bubbleTimer = null;
    var flipTimer = null;
    var pendingOpen = null;
    var lastBounceSound = 0;
    var dragPointerId = null;
    var positioned = false;

    function tr(text) {
        try {
            return global.I18n ? global.I18n.t(text) : text;
        } catch (e) {
            return text;
        }
    }

    function readFlag(key, defaultValue) {
        try {
            var value = global.localStorage.getItem(key);
            return value === null ? defaultValue : value !== '0';
        } catch (e) {
            return defaultValue;
        }
    }

    function writeFlag(key, enabled) {
        try {
            global.localStorage.setItem(key, enabled ? '1' : '0');
        } catch (e) { /* ignore */ }
    }

    function petEnabled() {
        return readFlag(STORAGE_ENABLED, true);
    }

    function soundEnabled() {
        return readFlag(STORAGE_SOUND, true);
    }

    function playSound(kind) {
        if (!soundEnabled()) return;

        // 隨機播放 D1-D3；grab/bounce 用較低音量，避免連續碰撞時太吵。
        var index = Math.floor(Math.random() * 3) + 1;
        var volume = kind === 'bounce' ? 0.22 : 0.45;
        var audio;
        try {
            audio = new Audio('pet/D' + index + '.wav');
            audio.volume = volume;
            var playback = audio.play();
            if (playback && typeof playback.catch === 'function') {
                playback.catch(function () { /* 使用者手勢限制或格式不支援時忽略 */ });
            }
            audio.addEventListener('ended', function () {
                audio.src = '';
            }, { once: true });
        } catch (e) { /* ignore */ }
    }

    function applyTransform() {
        if (!el) return;
        el.style.transform = 'translate(-50%, -50%) scale(' + scale + ') rotate(' + rotation + 'deg)';
        el.style.left = x + 'px';
        el.style.top = y + 'px';
        el.classList.toggle('dragging', isDragging);
        el.classList.toggle('animating', isAnimating && !isDragging);
    }

    function clampPosition() {
        var maxX = Math.max(MARGIN, global.innerWidth - MARGIN);
        var maxY = Math.max(MARGIN, global.innerHeight - MARGIN);
        x = Math.min(maxX, Math.max(MARGIN, x));
        y = Math.min(maxY, Math.max(MARGIN, y));
    }

    function placeInitial() {
        // In a WebView the first layout pass can briefly report a zero viewport.
        // Retry instead of leaving the pet stuck in the top-left corner.
        if (!global.innerWidth || !global.innerHeight) {
            global.setTimeout(placeInitial, 100);
            return;
        }
        x = Math.max(MARGIN, global.innerWidth - 62);
        y = Math.max(MARGIN, global.innerHeight - 118);
        positioned = true;
        applyTransform();
    }

    function stopAnimation() {
        if (rafId !== null) {
            global.cancelAnimationFrame(rafId);
            rafId = null;
        }
        isAnimating = false;
        applyTransform();
    }

    function recordPosition(px, py) {
        var now = Date.now();
        lastPositions.push({ x: px, y: py, time: now });
        if (lastPositions.length > 5) lastPositions.shift();
    }

    function calculateThrowVelocity() {
        vx = 0;
        vy = 0;
        if (lastPositions.length < 2) return;

        var totalWeight = 0;
        for (var i = lastPositions.length - 1; i > 0; i--) {
            var curr = lastPositions[i];
            var prev = lastPositions[i - 1];
            var dt = curr.time - prev.time;
            if (dt > 0) {
                var weight = i;
                vx += ((curr.x - prev.x) / dt * 16) * weight;
                vy += ((curr.y - prev.y) / dt * 16) * weight;
                totalWeight += weight;
            }
        }

        if (totalWeight > 0) {
            vx /= totalWeight;
            vy /= totalWeight;
        }

        var maxSpeed = 35;
        var speed = Math.sqrt(vx * vx + vy * vy);
        if (speed > maxSpeed) {
            var factor = maxSpeed / speed;
            vx *= factor;
            vy *= factor;
        }

        if (speed < 2 && lastPositions.length >= 3) {
            var last = lastPositions[lastPositions.length - 1];
            var first = lastPositions[0];
            var totalMove = Math.sqrt(
                Math.pow(last.x - first.x, 2) +
                Math.pow(last.y - first.y, 2)
            );
            if (totalMove > 30) {
                var span = last.time - first.time;
                if (span > 0) {
                    vx = (last.x - first.x) / span * 16;
                    vy = (last.y - first.y) / span * 16;
                }
            }
        }
    }

    function startPhysics() {
        var speed = Math.sqrt(vx * vx + vy * vy);
        if (speed < 1) return;

        stopAnimation();
        isAnimating = true;
        lastFrame = 0;

        var step = function (now) {
            if (!isAnimating) return;
            if (!lastFrame) lastFrame = now;
            var elapsed = Math.min(32, now - lastFrame);
            lastFrame = now;

            // 以 16ms 為一格的固定步進，避免不同螢幕更新率造成速度差異。
            var steps = Math.max(1, Math.round(elapsed / 16));
            for (var s = 0; s < steps; s++) {
                vx *= 0.92;
                vy *= 0.92;
                x += vx;
                y += vy;

                var bounced = false;
                if (x < MARGIN) {
                    x = MARGIN;
                    vx = -vx * 0.6;
                    bounced = true;
                } else if (x > global.innerWidth - MARGIN) {
                    x = global.innerWidth - MARGIN;
                    vx = -vx * 0.6;
                    bounced = true;
                }
                if (y < MARGIN) {
                    y = MARGIN;
                    vy = -vy * 0.6;
                    bounced = true;
                } else if (y > global.innerHeight - MARGIN) {
                    y = global.innerHeight - MARGIN;
                    vy = -vy * 0.6;
                    bounced = true;
                }

                if (bounced && (Math.abs(vx) > 2 || Math.abs(vy) > 2)) {
                    triggerBounceEffect();
                }

                rotation = Math.min(15, Math.max(-15, vx * 0.5));
            }

            applyTransform();

            if (Math.sqrt(vx * vx + vy * vy) < 0.8) {
                isAnimating = false;
                rotation = 0;
                clampPosition();
                applyTransform();
                rafId = null;
                return;
            }

            rafId = global.requestAnimationFrame(step);
        };

        rafId = global.requestAnimationFrame(step);
    }

    function triggerBounceEffect() {
        var now = Date.now();
        if (now - lastBounceSound < 140) return;
        lastBounceSound = now;
        el.classList.add('bounce');
        global.setTimeout(function () {
            el.classList.remove('bounce');
        }, 220);
        playSound('bounce');
    }

    function showBubble(text, duration) {
        if (!bubble || !bubbleText) return;
        bubbleText.textContent = text;
        bubble.classList.add('show');
        bubble.setAttribute('aria-hidden', 'false');
        if (bubbleTimer) global.clearTimeout(bubbleTimer);
        bubbleTimer = global.setTimeout(function () {
            hideBubble();
        }, duration || 2000);
    }

    function hideBubble() {
        if (!bubble) return;
        bubble.classList.remove('show');
        bubble.setAttribute('aria-hidden', 'true');
        if (bubbleTimer) {
            global.clearTimeout(bubbleTimer);
            bubbleTimer = null;
        }
    }

    function triggerFlip() {
        if (!img) return;
        img.classList.add('flipping');
        if (flipTimer) global.clearTimeout(flipTimer);
        flipTimer = global.setTimeout(function () {
            img.classList.remove('flipping');
        }, 620);
    }

    function randomItem(list) {
        return list[Math.floor(Math.random() * list.length)];
    }

    function openChat() {
        if (global.CatHealthChat && typeof global.CatHealthChat.open === 'function') {
            global.CatHealthChat.open();
        }
    }

    function handleClick() {
        triggerFlip();
        showBubble(tr(randomItem(TIPS)), 2200);
        playSound('random');

        if (pendingOpen) global.clearTimeout(pendingOpen);
        pendingOpen = global.setTimeout(function () {
            pendingOpen = null;
            hideBubble();
            openChat();
        }, 800);
    }

    function onPointerDown(event) {
        if (!petEnabled()) return;
        if (event.button !== undefined && event.button !== 0) return;

        event.preventDefault();
        stopAnimation();
        hideBubble();
        isDragging = true;
        scale = 1.15;
        rotation = 0;
        el.classList.add('dragging');
        applyTransform();

        dragPointerId = event.pointerId;
        if (el.setPointerCapture && event.pointerId !== undefined) {
            try { el.setPointerCapture(event.pointerId); } catch (e) { /* ignore */ }
        }

        touchStartX = event.clientX;
        touchStartY = event.clientY;
        touchStartTime = Date.now();
        hasMoved = false;
        lastPositions = [];
        recordPosition(event.clientX, event.clientY);
    }

    function onPointerMove(event) {
        if (!isDragging) return;
        if (dragPointerId !== null && event.pointerId !== dragPointerId) return;
        event.preventDefault();

        var moveDistance = Math.sqrt(
            Math.pow(event.clientX - touchStartX, 2) +
            Math.pow(event.clientY - touchStartY, 2)
        );
        if (moveDistance > 5) hasMoved = true;

        x = Math.max(8, Math.min(global.innerWidth - 8, event.clientX));
        y = Math.max(8, Math.min(global.innerHeight - 8, event.clientY));
        recordPosition(event.clientX, event.clientY);
        applyTransform();
    }

    function onPointerUp(event) {
        if (!isDragging) return;
        if (dragPointerId !== null && event.pointerId !== dragPointerId) return;

        var duration = Date.now() - touchStartTime;
        isDragging = false;
        scale = 1;
        dragPointerId = null;
        el.classList.remove('dragging');
        applyTransform();

        if (!hasMoved && duration < 300) {
            handleClick();
            return;
        }

        calculateThrowVelocity();
        var speed = Math.sqrt(vx * vx + vy * vy);
        if (speed > 15 && Math.random() < 0.4) {
            showBubble(tr(randomItem(THROW_TEXTS)), 2000);
        }
        playSound('random');
        startPhysics();
    }

    function onPointerCancel() {
        if (!isDragging) return;
        isDragging = false;
        dragPointerId = null;
        scale = 1;
        el.classList.remove('dragging');
        applyTransform();
    }

    function onKeyDown(event) {
        if (!petEnabled()) return;
        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            handleClick();
        }
    }

    function onResize() {
        if (!positioned) {
            placeInitial();
            return;
        }
        clampPosition();
        applyTransform();
    }

    function setEnabled(enabled) {
        writeFlag(STORAGE_ENABLED, enabled);
        if (!el) return;
        if (enabled) {
            el.style.display = 'block';
            if (!positioned) {
                placeInitial();
            } else {
                clampPosition();
                applyTransform();
            }
        } else {
            stopAnimation();
            hideBubble();
            el.style.display = 'none';
        }
        var toggle = document.getElementById('pet-enabled-toggle');
        if (toggle) toggle.checked = enabled;
    }

    function setSoundEnabled(enabled) {
        writeFlag(STORAGE_SOUND, enabled);
        var toggle = document.getElementById('pet-sound-toggle');
        if (toggle) toggle.checked = enabled;
    }

    function bindSettings() {
        var enabledToggle = document.getElementById('pet-enabled-toggle');
        var soundToggle = document.getElementById('pet-sound-toggle');

        if (enabledToggle) {
            enabledToggle.checked = petEnabled();
            enabledToggle.addEventListener('change', function () {
                setEnabled(this.checked);
            });
        }
        if (soundToggle) {
            soundToggle.checked = soundEnabled();
            soundToggle.addEventListener('change', function () {
                setSoundEnabled(this.checked);
            });
        }
    }

    function init() {
        if (initialized) return;
        initialized = true;

        el = document.getElementById('pet-float');
        img = document.getElementById('pet-image');
        bubble = document.getElementById('pet-bubble');
        bubbleText = document.getElementById('pet-bubble-text');
        if (!el || !img) return;

        el.setAttribute('aria-label', tr('打开 AI 健康助手'));
        el.setAttribute('title', tr('打开 AI 健康助手'));

        el.addEventListener('pointerdown', onPointerDown);
        el.addEventListener('pointermove', onPointerMove);
        el.addEventListener('pointerup', onPointerUp);
        el.addEventListener('pointercancel', onPointerCancel);
        el.addEventListener('keydown', onKeyDown);
        el.addEventListener('dragstart', function (e) { e.preventDefault(); });

        global.addEventListener('resize', onResize);

        if (!petEnabled()) {
            el.style.display = 'none';
        } else {
            placeInitial();
        }

        bindSettings();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init, { once: true });
    } else {
        init();
    }

    global.CatHealthPet = {
        init: init,
        openChat: openChat,
        setEnabled: setEnabled,
        setSoundEnabled: setSoundEnabled,
        isEnabled: petEnabled,
        isSoundEnabled: soundEnabled
    };

})(window);
