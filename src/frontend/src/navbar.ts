import { fetchAuthInfo } from './api';

/** Inject the navbar into the page and load user info. */
export async function renderNavbar(): Promise<void> {
    // Inject Fabric Core font for style consistency
    if (!document.querySelector('link[href*="segoe-ui"]')) {
        const fontLink = document.createElement('link');
        fontLink.rel = 'stylesheet';
        fontLink.href =
            'https://static2.sharepointonline.com/files/fabric/office-ui-fabric-core/11.0.0/css/fabric.min.css';
        document.head.appendChild(fontLink);
    }

    const currentPath = window.location.pathname.split('/').pop() || 'index.html';

    const navHTML = `
    <nav class="navbar">
        <div style="display: flex; align-items: center; width: 100%;">
            <a href="index.html" class="nav-brand">RM Analyzer</a>
            <div class="nav-links">
                <a href="index.html" class="nav-link ${currentPath === 'index.html' || currentPath === '' ? 'active' : ''}">Dashboard</a>
                <a href="savings.html" class="nav-link ${currentPath === 'savings.html' ? 'active' : ''}">Savings Calculator</a>
            </div>
            <div id="nav-user-info" class="nav-user"></div>
        </div>
    </nav>
    `;

    document.body.insertAdjacentHTML('afterbegin', navHTML);

    // Load auth info
    const authPayload = await fetchAuthInfo();
    if (authPayload?.clientPrincipal) {
        const userInfoEl = document.getElementById('nav-user-info');
        if (userInfoEl) {
            userInfoEl.innerText = `Hello, ${authPayload.clientPrincipal.userDetails}`;
        }
    }
}
