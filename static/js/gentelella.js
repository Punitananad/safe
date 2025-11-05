/**
 * Gentelella Admin Template JS
 * Core functionality for the Gentelella admin template
 */

document.addEventListener('DOMContentLoaded', function() {
  // Initialize sidebar toggle
  initSidebar();
  
  // Initialize panel tools
  initPanelTools();
  
  // Initialize tooltips
  initTooltips();
  
  // Initialize responsive tables
  initResponsiveTables();
});

/**
 * Initialize sidebar functionality
 */
function initSidebar() {
  // Fixed: Handle multiple possible toggle selectors
  const menuToggle = document.querySelector('.menu_toggle') || document.querySelector('#menu_toggle');
  if (menuToggle) {
    menuToggle.addEventListener('click', function(e) {
      e.preventDefault();
      const body = document.querySelector('body');
      
      // Fixed: Check if we're using the new layout or old layout
      const sidebar = document.querySelector('.sidebar') || document.querySelector('.left_col');
      const mainContent = document.querySelector('.main-content') || document.querySelector('.right_col');
      
      if (sidebar && mainContent) {
        // New layout with sidebar class
        if (window.innerWidth <= 768) {
          sidebar.classList.toggle('active');
        } else {
          if (sidebar.style.width === '60px') {
            sidebar.style.width = '230px';
            mainContent.style.marginLeft = '230px';
          } else {
            sidebar.style.width = '60px';
            mainContent.style.marginLeft = '60px';
          }
        }
      } else {
        // Fallback to original behavior
        if (body.classList.contains('nav-md')) {
          body.classList.remove('nav-md');
          body.classList.add('nav-sm');
          
          // Collapse opened child menus
          const openMenus = document.querySelectorAll('.side-menu li.active');
          openMenus.forEach(function(menu) {
            menu.classList.remove('active');
          });
        } else {
          body.classList.remove('nav-sm');
          body.classList.add('nav-md');
        }
      }
    });
  }
  
  // Fixed: Sidebar menu with better error handling
  const sideMenu = document.querySelectorAll('.side-menu li a');
  sideMenu.forEach(function(link) {
    link.addEventListener('click', function(e) {
      const parent = this.parentElement;
      
      if (parent && parent.classList.contains('active')) {
        e.preventDefault();
        parent.classList.remove('active');
        const childMenu = parent.querySelector('ul');
        if (childMenu) {
          slideUp(childMenu, 200);
        }
      } else if (parent) {
        // Check if has submenu
        const childMenu = parent.querySelector('ul');
        if (childMenu) {
          e.preventDefault();
          parent.classList.add('active');
          slideDown(childMenu, 200);
        }
      }
    });
  });
  
  // Fixed: Close mobile sidebar when clicking outside
  document.addEventListener('click', function(e) {
    const sidebar = document.querySelector('.sidebar');
    const menuToggle = document.querySelector('.menu_toggle') || document.querySelector('#menu_toggle');
    
    if (sidebar && menuToggle && window.innerWidth <= 768 && 
        !sidebar.contains(e.target) && 
        !menuToggle.contains(e.target) && 
        sidebar.classList.contains('active')) {
      sidebar.classList.remove('active');
    }
  });
}

/**
 * Initialize panel tools (collapse, close, etc)
 */
function initPanelTools() {
  // Panel toolbox
  const panelToolbox = document.querySelectorAll('.x_panel .collapse-link');
  panelToolbox.forEach(function(link) {
    link.addEventListener('click', function(e) {
      e.preventDefault();
      const panel = this.closest('.x_panel');
      const content = panel.querySelector('.x_content');
      const icon = this.querySelector('i');
      
      // Toggle content
      if (content.style.display === 'none' || content.style.display === '') {
        content.style.display = 'block';
        icon.className = 'fa fa-chevron-up';
      } else {
        content.style.display = 'none';
        icon.className = 'fa fa-chevron-down';
      }
    });
  });
  
  // Close panel
  const closePanel = document.querySelectorAll('.x_panel .close-link');
  closePanel.forEach(function(link) {
    link.addEventListener('click', function(e) {
      e.preventDefault();
      const panel = this.closest('.x_panel');
      panel.remove();
    });
  });
}

/**
 * Initialize tooltips
 */
function initTooltips() {
  const tooltips = document.querySelectorAll('[data-toggle="tooltip"]');
  tooltips.forEach(function(tooltip) {
    tooltip.addEventListener('mouseenter', function() {
      const tip = document.createElement('div');
      tip.className = 'tooltip';
      tip.textContent = this.getAttribute('title');
      document.body.appendChild(tip);
      
      const rect = this.getBoundingClientRect();
      tip.style.top = rect.top - tip.offsetHeight - 5 + 'px';
      tip.style.left = rect.left + (rect.width / 2) - (tip.offsetWidth / 2) + 'px';
      tip.classList.add('show');
      
      this.addEventListener('mouseleave', function() {
        tip.remove();
      }, { once: true });
    });
  });
}

/**
 * Initialize responsive tables
 */
function initResponsiveTables() {
  const tables = document.querySelectorAll('table.responsive');
  tables.forEach(function(table) {
    const headers = Array.from(table.querySelectorAll('thead th')).map(th => th.textContent);
    const cells = table.querySelectorAll('tbody td');
    
    cells.forEach(function(cell, index) {
      const headerIndex = index % headers.length;
      cell.setAttribute('data-title', headers[headerIndex]);
    });
  });
}

/**
 * Slide down animation
 */
function slideDown(element, duration) {
  element.style.height = 'auto';
  const height = element.offsetHeight;
  element.style.height = '0px';
  element.style.opacity = '0';
  element.style.overflow = 'hidden';
  element.style.transition = `height ${duration}ms ease-in-out, opacity ${duration}ms ease-in-out`;
  
  setTimeout(() => {
    element.style.height = height + 'px';
    element.style.opacity = '1';
  }, 10);
  
  setTimeout(() => {
    element.style.height = 'auto';
  }, duration);
}

/**
 * Slide up animation
 */
function slideUp(element, duration) {
  element.style.height = element.offsetHeight + 'px';
  element.style.transition = `height ${duration}ms ease-in-out, opacity ${duration}ms ease-in-out`;
  element.style.overflow = 'hidden';
  
  setTimeout(() => {
    element.style.height = '0px';
    element.style.opacity = '0';
  }, 10);
  
  setTimeout(() => {
    element.style.display = 'none';
  }, duration);
}