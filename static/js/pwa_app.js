// PWA Service Worker Registration & Update Detection
let deferredPrompt;

if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/service-worker.js').then(reg => {


            // Check if there is already a waiting worker (Update ready but waiting)
            if (reg.waiting) {
                showUpdateToast();
            }

            // Check for updates periodically
            reg.addEventListener('updatefound', () => {
                const newWorker = reg.installing;
                newWorker.addEventListener('statechange', () => {
                    // If installed and we have a controller, it's an update, not first load
                    if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                        showUpdateToast();
                    }
                });
            });
        });
    });
}

// Handle PWA Install Prompt
window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPrompt = e;
    showInstallToast();
});

window.addEventListener('appinstalled', (evt) => {
    hideInstallToast();
});

function showUpdateToast() {
    window.dispatchEvent(new CustomEvent('pwa-update-found'));
}

function showInstallToast() {
    window.dispatchEvent(new CustomEvent('pwa-installable'));
}

function hideInstallToast() {
    window.dispatchEvent(new CustomEvent('pwa-install-hide'));
}

async function installPWA() {
    if (deferredPrompt) {
        deferredPrompt.prompt();
        const { outcome } = await deferredPrompt.userChoice;
        deferredPrompt = null;
        hideInstallToast();
    }
}