async function getUserInfo() {
    try {
        const response = await fetch('/.auth/me');
        const payload = await response.json();
        const { clientPrincipal } = payload;
        if (clientPrincipal) {
            document.getElementById('user-info').innerText = `Hello, ${clientPrincipal.userDetails}`;
        }
    } catch (error) {
        console.error('No auth info found (local dev?)');
    }
}

async function uploadFile() {
    const fileInput = document.getElementById('fileInput');
    const statusDiv = document.getElementById('status');
    const btn = document.getElementById('uploadBtn');

    if (!fileInput.files.length) {
        statusDiv.innerText = 'Please select a file.';
        return;
    }

    const file = fileInput.files[0];
    btn.disabled = true;
    statusDiv.innerText = 'Uploading...';

    const formData = new FormData();
    formData.append('file', file);

    try {
        // Upload directly to our Backend API (secured by SWA Auth)
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            statusDiv.innerText = 'Upload successful! Analysis will run shortly.';
        } else {
            const errorText = await response.text();
            throw new Error(errorText || 'Upload failed');
        }
    } catch (error) {
        statusDiv.innerText = `Error: ${error.message}`;
    } finally {
        btn.disabled = false;
    }
}

getUserInfo();