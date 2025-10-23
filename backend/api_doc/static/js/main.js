// API Documentation Interactive Features

document.addEventListener('DOMContentLoaded', function() {
    // Add copy buttons to all code blocks
    addCopyButtons();
    
    // Highlight current nav item
    highlightCurrentNav();
    
    // Add smooth scrolling
    addSmoothScrolling();
});

function addCopyButtons() {
    const codeBlocks = document.querySelectorAll('.code-block pre');
    
    codeBlocks.forEach(block => {
        const button = document.createElement('button');
        button.className = 'copy-button';
        button.textContent = 'Copy';
        
        button.addEventListener('click', function() {
            const code = block.textContent;
            
            navigator.clipboard.writeText(code).then(() => {
                button.textContent = 'Copied!';
                button.classList.add('copied');
                
                setTimeout(() => {
                    button.textContent = 'Copy';
                    button.classList.remove('copied');
                }, 2000);
            }).catch(err => {
                console.error('Failed to copy:', err);
                button.textContent = 'Failed';
                setTimeout(() => {
                    button.textContent = 'Copy';
                }, 2000);
            });
        });
        
        // Insert button before the code block
        const wrapper = block.parentElement;
        if (wrapper.querySelector('.code-header')) {
            wrapper.querySelector('.code-header').appendChild(button);
        } else {
            const header = document.createElement('div');
            header.className = 'code-header';
            header.appendChild(button);
            wrapper.insertBefore(header, block);
        }
    });
}

function highlightCurrentNav() {
    const currentPath = window.location.pathname;
    const navLinks = document.querySelectorAll('.nav a');
    
    navLinks.forEach(link => {
        if (link.getAttribute('href') === currentPath) {
            link.classList.add('active');
        }
    });
}

function addSmoothScrolling() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
}

// Try Example functionality
function tryExample(url, method = 'GET') {
    const baseUrl = window.location.origin;
    const fullUrl = baseUrl + url;
    
    fetch(fullUrl, { method: method })
        .then(response => response.json())
        .then(data => {
            alert('Response received! Check the browser console for details.');
            console.log('API Response:', data);
        })
        .catch(error => {
            alert('Error: ' + error.message);
            console.error('API Error:', error);
        });
}
