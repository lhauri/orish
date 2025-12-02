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
});
