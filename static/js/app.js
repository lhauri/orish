document.addEventListener('DOMContentLoaded', () => {
    if (window.lucide) {
        window.lucide.createIcons();
    }

    const menuToggle = document.querySelector('.menu-toggle');
    const navLinks = document.getElementById('primary-nav');
    if (menuToggle && navLinks) {
        menuToggle.addEventListener('click', () => {
            const isOpen = navLinks.dataset.open === 'true';
            navLinks.dataset.open = (!isOpen).toString();
            menuToggle.setAttribute('aria-expanded', (!isOpen).toString());
        });
    }

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
