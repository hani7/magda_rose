// Service Worker Register 
if ('serviceWorker' in navigator) {
  window.addEventListener('load', function () {
    navigator.serviceWorker.register('service-worker.js')
      .then(registration => {
        //console.log('Service Worker is registered', registration);
      })
      .catch(err => {
        console.error('Registration failed:', err);
      });
  });
}

// PWA Installation
let deferredPrompt;

window.addEventListener('beforeinstallprompt', (e) => {
   e.preventDefault();
   deferredPrompt = e;
});

const installButton = document.getElementById('installSuha');

if (installButton) {
   function updateInstallButton() {
       if (window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true) {
           installButton.textContent = 'Installed';
       } else {
           installButton.textContent = 'Install Now';
       }
   }

   installButton.addEventListener('click', async () => {
       if (installButton.textContent === 'Installed') {
           return;
       }

       if (deferredPrompt) {
           deferredPrompt.prompt();
           const {
               outcome
           } = await deferredPrompt.userChoice;
           if (outcome === 'accepted') {
               installButton.textContent = 'Installed';
           } else {
               installButton.textContent = 'Install Now';
           }
           deferredPrompt = null;
       }
   });

   updateInstallButton();
   window.matchMedia('(display-mode: standalone)').addEventListener('change', updateInstallButton);
}