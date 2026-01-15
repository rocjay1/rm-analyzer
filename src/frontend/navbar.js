async function renderNavbar() {
    // Inject font (optional, but good for style consistency)
    if (!document.querySelector('link[href*="segoe-ui"]')) {
        const fontLink = document.createElement('link');
        fontLink.rel = 'stylesheet';
        fontLink.href = 'https://static2.sharepointonline.com/files/fabric/office-ui-fabric-core/11.0.0/css/fabric.min.css'; // Using Fabric Core for fonts/icons if needed later
        document.head.appendChild(fontLink);
    }

    const currentPath = window.location.pathname.split('/').pop() || 'index.html';

    const navHTML = `
    <nav class="navbar">
        <div style="display: flex; align-items: center; width: 100%;">
            <a href="index.html" class="nav-brand">RM Analyzer</a>
            <div class="nav-links">
                <a href="index.html" class="nav-link ${currentPath === 'index.html' || currentPath === '' ? 'active' : ''}">Upload</a>
                <a href="savings.html" class="nav-link ${currentPath === 'savings.html' ? 'active' : ''}">Savings Calculator</a>
            </div>
            <div id="nav-user-info" class="nav-user"></div>
        </div>
    </nav>
    `;

    document.body.insertAdjacentHTML('afterbegin', navHTML);

    await updateNavUserInfo();
}

async function updateNavUserInfo() {
    try {
        const response = await fetch('/.auth/me');
        if (response.ok) {
            const payload = await response.json();
            const { clientPrincipal } = payload;
            if (clientPrincipal) {
                document.getElementById('nav-user-info').innerText = `Hello, ${clientPrincipal.userDetails}`;
            }
        }
    } catch (error) {
        console.log('No auth info found (local dev?)');
    }
}

// Auto-render on load
document.addEventListener('DOMContentLoaded', renderNavbar);
