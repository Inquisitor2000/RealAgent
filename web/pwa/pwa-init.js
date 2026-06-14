/**
 * RealAgent PWA Initialization Script (Clean Version)
 * Handles service worker registration and app installation only
 */

(function() {
  'use strict';
  
  // Configuration
  const CONFIG = {
    swPath: '/pwa/service-worker.js',
    swScope: '/'
  };
  
  // Check if PWA is supported
  if (!('serviceWorker' in navigator)) {
    console.log('Service Workers not supported');
    return;
  }
  
  // Initialize PWA features when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializePWA);
  } else {
    initializePWA();
  }
  
  async function initializePWA() {
    try {
      // Register service worker
      const registration = await registerServiceWorker();
      
      // Handle app installation
      handleAppInstallation();
      
      // Add offline indicator
      addOfflineIndicator();
      
      // Handle updates
      handleServiceWorkerUpdates(registration);
      
      // Initialize favorites system
      initializeFavorites();
      
      // Add PWA features to UI
      enhanceUIForPWA();
      
    } catch (error) {
      console.error('PWA initialization failed:', error);
    }
  }
  
  // Register service worker
  async function registerServiceWorker() {
    try {
      const registration = await navigator.serviceWorker.register(CONFIG.swPath, {
        scope: CONFIG.swScope
      });
      
      console.log('Service Worker registered:', registration);
      
      // Check for updates periodically
      setInterval(() => {
        registration.update();
      }, 60 * 60 * 1000); // Check every hour
      
      return registration;
    } catch (error) {
      console.error('Service Worker registration failed:', error);
      throw error;
    }
  }
  
  // Get current listing ID from URL
  function getListingId() {
    const path = window.location.pathname;
    // Match patterns like /999_md_102217451/ or /999-md-102217451/
    const match = path.match(/\/([^\/]+)/);
    return match ? match[1] : null;
  }
  
  // Handle app installation
  function handleAppInstallation() {
    let deferredPrompt;
    
    window.addEventListener('beforeinstallprompt', (e) => {
      e.preventDefault();
      deferredPrompt = e;
      showInstallButton(deferredPrompt);
    });
    
    window.addEventListener('appinstalled', () => {
      console.log('PWA was installed');
      hideInstallButton();
      // Track installation
      if (typeof gtag !== 'undefined') {
        gtag('event', 'pwa_install', {
          event_category: 'engagement',
          event_label: getListingId()
        });
      }
    });
  }
  
  // Show install button
  function showInstallButton(deferredPrompt) {
    const installBtn = document.createElement('button');
    installBtn.id = 'pwa-install-btn';
    installBtn.innerHTML = `
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
        <polyline points="7,10 12,15 17,10"/>
        <line x1="12" y1="15" x2="12" y2="3"/>
      </svg>
      Install App
    `;
    
    installBtn.style.cssText = `
      position: fixed;
      bottom: 20px;
      right: 20px;
      background: #059669;
      color: white;
      border: none;
      border-radius: 50px;
      padding: 12px 20px;
      display: flex;
      align-items: center;
      gap: 8px;
      cursor: pointer;
      box-shadow: 0 4px 6px rgba(0,0,0,0.1);
      z-index: 1000;
      transition: all 0.3s ease;
      font-family: 'Inter', sans-serif;
    `;
    
    installBtn.addEventListener('click', async () => {
      if (deferredPrompt) {
        deferredPrompt.prompt();
        const { outcome } = await deferredPrompt.userChoice;
        console.log(`User response to install prompt: ${outcome}`);
        deferredPrompt = null;
        hideInstallButton();
      }
    });
    
    document.body.appendChild(installBtn);
  }
  
  // Hide install button
  function hideInstallButton() {
    const installBtn = document.getElementById('pwa-install-btn');
    if (installBtn) {
      installBtn.style.opacity = '0';
      setTimeout(() => installBtn.remove(), 300);
    }
  }
  
  // Add offline indicator
  function addOfflineIndicator() {
    const indicator = document.createElement('div');
    indicator.id = 'pwa-offline-indicator';
    indicator.innerHTML = `
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor">
        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
        <circle cx="12" cy="12" r="3"/>
      </svg>
      You're offline
    `;
    
    indicator.style.cssText = `
      position: fixed;
      top: 20px;
      left: 50%;
      transform: translateX(-50%);
      background: #dc2626;
      color: white;
      padding: 8px 16px;
      border-radius: 20px;
      display: none;
      align-items: center;
      gap: 8px;
      z-index: 1001;
      font-size: 14px;
      font-family: 'Inter', sans-serif;
    `;
    
    document.body.appendChild(indicator);
    
    // Show/hide based on connection status
    function updateConnectionStatus() {
      if (navigator.onLine) {
        indicator.style.display = 'none';
      } else {
        indicator.style.display = 'flex';
      }
    }
    
    window.addEventListener('online', updateConnectionStatus);
    window.addEventListener('offline', updateConnectionStatus);
    updateConnectionStatus();
  }
  
  // Handle service worker updates
  function handleServiceWorkerUpdates(registration) {
    registration.addEventListener('updatefound', () => {
      const newWorker = registration.installing;
      
      newWorker.addEventListener('statechange', () => {
        if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
          showUpdateNotification(newWorker);
        }
      });
    });
  }
  
  // Show update notification
  function showUpdateNotification(newWorker) {
    const updateBar = document.createElement('div');
    updateBar.innerHTML = `
      <span>New version available!</span>
      <button id="pwa-update-btn">Update</button>
      <button id="pwa-dismiss-btn">×</button>
    `;
    
    updateBar.style.cssText = `
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      background: #3b82f6;
      color: white;
      padding: 12px 20px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      z-index: 1002;
      font-family: 'Inter', sans-serif;
    `;
    
    document.body.appendChild(updateBar);
    
    document.getElementById('pwa-update-btn').addEventListener('click', () => {
      newWorker.postMessage({ type: 'SKIP_WAITING' });
      window.location.reload();
    });
    
    document.getElementById('pwa-dismiss-btn').addEventListener('click', () => {
      updateBar.remove();
    });
  }
  
  // Initialize favorites system
  function initializeFavorites() {
    const favoriteBtn = document.createElement('button');
    favoriteBtn.id = 'pwa-favorite-btn';
    favoriteBtn.innerHTML = `
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor">
        <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
      </svg>
    `;
    
    favoriteBtn.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      background: rgba(255,255,255,0.9);
      border: 1px solid #e5e7eb;
      border-radius: 50%;
      width: 48px;
      height: 48px;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      z-index: 1000;
      transition: all 0.3s ease;
      backdrop-filter: blur(10px);
    `;
    
    const listingId = getListingId();
    if (listingId) {
      const favorites = JSON.parse(localStorage.getItem('pwa-favorites') || '[]');
      const isFavorite = favorites.includes(listingId);
      
      updateFavoriteButton(favoriteBtn, isFavorite);
      
      favoriteBtn.addEventListener('click', () => {
        toggleFavorite(listingId, favoriteBtn);
      });
      
      document.body.appendChild(favoriteBtn);
    }
  }
  
  // Toggle favorite status
  function toggleFavorite(listingId, button) {
    const favorites = JSON.parse(localStorage.getItem('pwa-favorites') || '[]');
    const index = favorites.indexOf(listingId);
    
    if (index > -1) {
      favorites.splice(index, 1);
    } else {
      favorites.push(listingId);
    }
    
    localStorage.setItem('pwa-favorites', JSON.stringify(favorites));
    updateFavoriteButton(button, index === -1);
  }
  
  // Update favorite button appearance
  function updateFavoriteButton(button, isFavorite) {
    const svg = button.querySelector('svg');
    if (isFavorite) {
      svg.style.fill = '#dc2626';
      svg.style.stroke = '#dc2626';
      button.style.background = 'rgba(220, 38, 38, 0.1)';
    } else {
      svg.style.fill = 'none';
      svg.style.stroke = '#6b7280';
      button.style.background = 'rgba(255,255,255,0.9)';
    }
  }
  
  // Enhance UI for PWA
  function enhanceUIForPWA() {
    // Add PWA-specific styles
    const style = document.createElement('style');
    style.textContent = `
      @media (display-mode: standalone) {
        body {
          padding-top: env(safe-area-inset-top);
          padding-bottom: env(safe-area-inset-bottom);
        }
        
        .pwa-standalone-indicator {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          height: env(safe-area-inset-top);
          background: var(--bg);
          z-index: 999;
        }
      }
      
      .pwa-button {
        user-select: none;
        -webkit-tap-highlight-color: transparent;
      }
    `;
    
    document.head.appendChild(style);
    
    // Add standalone indicator for PWA mode
    if (window.matchMedia('(display-mode: standalone)').matches) {
      const indicator = document.createElement('div');
      indicator.className = 'pwa-standalone-indicator';
      document.body.appendChild(indicator);
    }
  }
  
})();
