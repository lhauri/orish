document.addEventListener('DOMContentLoaded', () => {
    if (window.lucide) {
        window.lucide.createIcons();
    }

    const menuToggle = document.querySelector('.menu-toggle');
    const navLinks = document.getElementById('primary-nav');
    const dropdowns = Array.from(document.querySelectorAll('.nav-dropdown'));

    const closeDropdown = dropdown => {
        dropdown.dataset.open = 'false';
        const trigger = dropdown.querySelector('.dropdown-trigger');
        if (trigger) {
            trigger.setAttribute('aria-expanded', 'false');
        }
    };

    const closeAllDropdowns = () => dropdowns.forEach(closeDropdown);

    dropdowns.forEach(dropdown => {
        const trigger = dropdown.querySelector('.dropdown-trigger');
        if (!trigger) {
            return;
        }
        trigger.addEventListener('click', event => {
            event.preventDefault();
            const isOpen = dropdown.dataset.open === 'true';
            closeAllDropdowns();
            dropdown.dataset.open = (!isOpen).toString();
            trigger.setAttribute('aria-expanded', (!isOpen).toString());
        });
    });

    document.addEventListener('click', event => {
        dropdowns.forEach(dropdown => {
            if (!dropdown.contains(event.target)) {
                closeDropdown(dropdown);
            }
        });
    });

    document.addEventListener('keydown', event => {
        if (event.key === 'Escape') {
            closeAllDropdowns();
        }
    });

    if (menuToggle && navLinks) {
        menuToggle.addEventListener('click', () => {
            const isOpen = navLinks.dataset.open === 'true';
            navLinks.dataset.open = (!isOpen).toString();
            menuToggle.setAttribute('aria-expanded', (!isOpen).toString());
            if (!isOpen) {
                closeAllDropdowns();
            }
        });
    }

    const forms = Array.from(document.querySelectorAll('form'));
    forms.forEach(form => {
        if (form.dataset.skipLoading === 'true') {
            return;
        }
        form.addEventListener('submit', event => {
            if (form.dataset.ajaxSubmitting === 'true') {
                return;
            }
            const submitButton =
                form.querySelector('button[type="submit"].btn') ||
                form.querySelector('button.btn:not([type])');
            if (submitButton && !submitButton.classList.contains('loading')) {
                submitButton.classList.add('loading');
                submitButton.setAttribute('aria-busy', 'true');
                submitButton.setAttribute('data-loading', 'true');
            }
            if (form.dataset.finalSubmit === 'true') {
                form.classList.add('show-correcting');
            }
        });
    });

    const pushFlash = (message, category = 'info') => {
        let container = document.querySelector('.flash-container');
        if (!container) {
            container = document.createElement('div');
            container.className = 'flash-container';
            document.querySelector('.content')?.prepend(container);
        }
        const flash = document.createElement('div');
        flash.className = `flash flash-${category}`;
        flash.textContent = message;
        container.appendChild(flash);
        setTimeout(() => {
            flash.classList.add('fade');
            flash.addEventListener('transitionend', () => flash.remove(), { once: true });
        }, 3500);
    };

    const deleteForms = Array.from(document.querySelectorAll('.js-delete-user'));
    deleteForms.forEach(form => {
        form.addEventListener('submit', event => {
            event.preventDefault();
            const username = form.dataset.userName || 'this user';
            if (!window.confirm(`Delete ${username}? This removes their quiz and exam history.`)) {
                return;
            }
            const formData = new FormData(form);
            form.dataset.ajaxSubmitting = 'true';
            const submitButton = form.querySelector('button');
            if (submitButton) {
                submitButton.classList.add('loading');
            }
            fetch(form.action || window.location.pathname, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                },
            })
                .then(resp => resp.json())
                .then(data => {
                    if (data.status === 'ok') {
                        const row = form.closest('tr');
                        if (row) {
                            row.remove();
                        }
                        pushFlash(data.message || 'User deleted.', 'success');
                    } else {
                        pushFlash(data.message || 'Something went wrong.', 'danger');
                    }
                })
                .catch(() => {
                    pushFlash('Could not delete user. Please try again.', 'danger');
                })
                .finally(() => {
                    if (submitButton) {
                        submitButton.classList.remove('loading');
                    }
                    form.dataset.ajaxSubmitting = 'false';
                });
        });
    });

    document.querySelectorAll('form[data-enter-submit="true"]').forEach(form => {
        form.addEventListener('keydown', event => {
            const target = event.target;
            if (
                event.key === 'Enter' &&
                !event.shiftKey &&
                target.tagName === 'TEXTAREA'
            ) {
                event.preventDefault();
                form.requestSubmit();
            }
        });
    });

    const requiresValidation = document.querySelectorAll('form[data-validate="true"]');
    requiresValidation.forEach(form => {
        const submitButton = form.querySelector('button[type="submit"]') || form.querySelector('button');
        if (!submitButton) {
            return;
        }
        const requiredFields = Array.from(form.querySelectorAll('[required]'));
        const isFieldComplete = field => {
            if (field.disabled) {
                return true;
            }
            if (field.type === 'checkbox' || field.type === 'radio') {
                return field.checked;
            }
            return Boolean(field.value && field.value.trim().length > 0);
        };
        const toggleState = () => {
            const isValid = requiredFields.every(isFieldComplete);
            submitButton.disabled = !isValid;
            if (isValid) {
                submitButton.classList.remove('disabled');
            } else {
                submitButton.classList.add('disabled');
            }
        };
        form.addEventListener('input', toggleState);
        form.addEventListener('change', toggleState);
        toggleState();
    });

    const mindmap = document.getElementById('mindmap');
    if (mindmap) {
        const center = mindmap.querySelector('.node.center');
        const nodes = mindmap.querySelectorAll('.node:not(.center)');
        const radius = 130;
        nodes.forEach((node, index) => {
            const angle = (index / nodes.length) * 2 * Math.PI;
            node.style.top = `${50 + Math.sin(angle) * (radius / 2)}%`;
            node.style.left = `${50 + Math.cos(angle) * (radius / 1.6)}%`;
            const icon = node.dataset.icon;
            node.innerHTML = `<i data-lucide="${icon}"></i> ${node.textContent.trim()}`;
        });
        if (window.lucide) {
            window.lucide.createIcons();
        }
        center.innerHTML = `<i data-lucide="${center.dataset.icon}"></i> ${center.textContent.trim()}`;
    }

    const aiWidget = document.querySelector('.ai-widget');
    if (aiWidget) {
        const launcher = aiWidget.querySelector('.ai-launcher');
        const panel = aiWidget.querySelector('.ai-panel');
        const closeButton = aiWidget.querySelector('.ai-panel-close');
        const form = aiWidget.querySelector('[data-role="form"]');
        const textarea = form?.querySelector('textarea');
        const messagesEl = aiWidget.querySelector('[data-role="messages"]');
        const statusEl = aiWidget.querySelector('[data-role="status"]');
        const statusIndicator = aiWidget.querySelector('.ai-status-indicator');
        const state = { open: false, busy: false, assistantBubble: null };

        const togglePanel = open => {
            state.open = open;
            aiWidget.dataset.open = open.toString();
            panel.dataset.open = open.toString();
            panel.setAttribute('aria-hidden', (!open).toString());
            launcher.setAttribute('aria-expanded', open.toString());
            if (open && textarea) {
                setTimeout(() => textarea.focus(), 100);
            }
        };

        const appendMessage = (role, text, extraClass = '') => {
            if (!messagesEl) {
                return;
            }
            const bubble = document.createElement('div');
            bubble.className = `ai-message ai-message-${role}`;
            if (extraClass) {
                bubble.classList.add(extraClass);
            }
            bubble.textContent = text;
            messagesEl.appendChild(bubble);
            messagesEl.scrollTop = messagesEl.scrollHeight;
            return bubble;
        };

        const appendProgress = message => {
            appendMessage('assistant', message, 'ai-message-progress');
        };

        const ensureAssistantBubble = () => {
            if (!state.assistantBubble) {
                state.assistantBubble = appendMessage('assistant', '');
            }
            return state.assistantBubble;
        };

        const appendChunk = chunk => {
            const bubble = ensureAssistantBubble();
            if (!bubble) {
                return;
            }
            const trimmed = chunk?.trim();
            if (!trimmed) {
                return;
            }
            bubble.textContent = `${bubble.textContent} ${trimmed}`.trim();
            messagesEl.scrollTop = messagesEl.scrollHeight;
        };

        const describeAction = action => {
            const status = action.status || 'pending';
            if (action.message) {
                return action.message;
            }
            if (status === 'forbidden' || status === 'error') {
                return action.message || 'Action could not be completed.';
            }
            if (action.type === 'create_exam' && action.title) {
                return `Created exam "${action.title}" (${action.category}).`;
            }
            if (action.type === 'create_question' && action.prompt) {
                return `Added ${action.category} question: ${action.prompt}.`;
            }
            if (action.type === 'create_group' && action.title) {
                return `New group "${action.title}" ready to share.`;
            }
            if (action.type === 'create_user' && action.username) {
                return `Created ${action.role} account for ${action.username}.`;
            }
            if (action.type === 'navigate' && (action.label || action.url)) {
                return `Navigate to ${action.label || action.url}.`;
            }
            return action.message || `${action.type || 'action'} (${status})`;
        };

        const renderActions = actions => {
            if (!messagesEl || !actions || !actions.length) {
                return;
            }
            const list = document.createElement('ul');
            list.className = 'ai-action-list';
            actions.forEach(action => {
                const item = document.createElement('li');
                const message = describeAction(action);
                item.textContent = message;
                if (action.url) {
                    const link = document.createElement('a');
                    link.href = action.url;
                    link.textContent = action.label || 'Open link';
                    link.target = '_self';
                    item.appendChild(document.createTextNode(' '));
                    item.appendChild(link);
                }
                if (typeof pushFlash === 'function') {
                    const level = action.status === 'error' ? 'danger' : 'success';
                    pushFlash(message, level);
                }
                list.appendChild(item);
            });
            messagesEl.appendChild(list);
            messagesEl.scrollTop = messagesEl.scrollHeight;
        };

        const updateStatus = (text, mode = 'ready') => {
            if (statusEl) {
                statusEl.textContent = text || '';
            }
            if (statusIndicator) {
                statusIndicator.setAttribute('data-state', mode);
            }
        };

        const handleEvent = event => {
            if (!event || typeof event !== 'object') {
                return;
            }
            switch (event.type) {
                case 'status':
                    updateStatus(event.message, 'thinking');
                    break;
                case 'progress':
                    appendProgress(event.message);
                    updateStatus(event.message, 'thinking');
                    break;
                case 'chunk':
                    appendChunk(event.content || '');
                    updateStatus('Responding…', 'thinking');
                    break;
                case 'done':
                    updateStatus('Ready for another question.', 'ready');
                    state.assistantBubble = null;
                    renderActions(event.actions);
                    if (event.navigate_to) {
                        appendProgress('Taking you to the requested page…');
                        setTimeout(() => {
                            window.location.href = event.navigate_to;
                        }, 1200);
                    }
                    break;
                case 'error':
                    updateStatus(event.message, 'error');
                    appendMessage('assistant', event.message || 'The assistant is unavailable.');
                    state.assistantBubble = null;
                    break;
                default:
                    break;
            }
        };

        const streamAssistant = async payload => {
            const headers = { 'Content-Type': 'application/json' };
            if (window.ORISH?.csrfToken) {
                headers['X-CSRFToken'] = window.ORISH.csrfToken;
            }
            const response = await fetch('/ai/assistant', {
                method: 'POST',
                headers,
                body: JSON.stringify(payload),
            });
            if (!response.ok || !response.body) {
                throw new Error('Assistant is busy. Please try again.');
            }
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            while (true) {
                const { value, done } = await reader.read();
                if (done) {
                    break;
                }
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';
                lines.forEach(line => {
                    if (!line.trim()) {
                        return;
                    }
                    try {
                        handleEvent(JSON.parse(line));
                    } catch {
                        // ignore malformed chunk
                    }
                });
            }
            if (buffer.trim()) {
                try {
                    handleEvent(JSON.parse(buffer));
                } catch {
                    // ignore leftover chunk
                }
            }
        };

        launcher?.addEventListener('click', () => {
            togglePanel(!state.open);
        });
        closeButton?.addEventListener('click', () => togglePanel(false));

        form?.addEventListener('submit', event => {
            event.preventDefault();
            if (state.busy) {
                return;
            }
            const text = textarea?.value.trim();
            if (!text) {
                return;
            }
            appendMessage('user', text);
            textarea.value = '';
            updateStatus('Thinking…', 'thinking');
            state.assistantBubble = null;
            state.busy = true;
            streamAssistant({ message: text })
                .catch(error => {
                    updateStatus(error.message, 'error');
                    appendMessage('assistant', error.message);
                    state.assistantBubble = null;
                })
                .finally(() => {
                    state.busy = false;
                });
        });
    }
});
