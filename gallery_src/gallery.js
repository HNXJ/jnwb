document.addEventListener('DOMContentLoaded', async () => {
    const galleryGrid = document.getElementById('gallery-grid');
    const searchInput = document.getElementById('gallery-search');
    const resultsCount = document.getElementById('results-count');
    const resetBtn = document.getElementById('reset-filters');
    
    let galleryData = [];
    let filters = {
        signal: new Set(),
        time: new Set(),
        analysis: new Set(),
        type: new Set()
    };

    try {
        const response = await fetch('manifests/gallery_manifest.json');
        const manifest = await response.json();
        galleryData = manifest.items;
        
        initFilters();
        renderGallery();
    } catch (err) {
        console.error('Failed to load manifest:', err);
        galleryGrid.innerHTML = `<p class="error">Error loading gallery manifest. Please check the console.</p>`;
    }

    function initFilters() {
        const categories = {
            signal: document.getElementById('filter-signal'),
            time: document.getElementById('filter-time'),
            analysis: document.getElementById('filter-analysis'),
            type: document.getElementById('filter-type')
        };

        const uniqueValues = {
            signal: new Set(),
            time: new Set(),
            analysis: new Set(),
            type: new Set()
        };

        galleryData.forEach(item => {
            item.tags.signal.forEach(v => uniqueValues.signal.add(v));
            item.tags.time.forEach(v => uniqueValues.time.add(v));
            item.tags.analysis.forEach(v => uniqueValues.analysis.add(v));
            uniqueValues.type.add(item.type);
        });

        Object.keys(categories).forEach(key => {
            const container = categories[key];
            Array.from(uniqueValues[key]).sort().forEach(val => {
                const chip = document.createElement('div');
                chip.className = 'filter-chip';
                chip.textContent = val;
                chip.onclick = () => toggleFilter(key, val, chip);
                container.appendChild(chip);
            });
        });
    }

    function toggleFilter(key, val, element) {
        if (filters[key].has(val)) {
            filters[key].delete(val);
            element.classList.remove('active');
        } else {
            filters[key].add(val);
            element.classList.add('active');
        }
        renderGallery();
    }

    function renderGallery() {
        const query = searchInput.value.toLowerCase();
        
        const filtered = galleryData.filter(item => {
            const matchesSearch = item.name.toLowerCase().includes(query) || 
                                 item.rel_path.toLowerCase().includes(query);
            
            const matchesSignal = filters.signal.size === 0 || item.tags.signal.some(v => filters.signal.has(v));
            const matchesTime = filters.time.size === 0 || item.tags.time.some(v => filters.time.has(v));
            const matchesAnalysis = filters.analysis.size === 0 || item.tags.analysis.some(v => filters.analysis.has(v));
            const matchesType = filters.type.size === 0 || filters.type.has(item.type);

            return matchesSearch && matchesSignal && matchesTime && matchesAnalysis && matchesType;
        });

        galleryGrid.innerHTML = '';
        filtered.forEach(item => {
            const card = document.createElement('div');
            card.className = 'card';
            
            let mediaHtml = '';
            if (['png', 'jpg', 'jpeg', 'svg'].includes(item.type)) {
                mediaHtml = `<img src="${item.rel_path}" alt="${item.name}">`;
            } else if (item.type === 'html') {
                mediaHtml = `<div class="file-icon">📊</div><div class="plotly-badge">PLOTLY</div>`;
            } else if (item.type === 'pdf') {
                mediaHtml = `<div class="file-icon">📄</div>`;
            } else {
                mediaHtml = `<div class="file-icon">📁</div>`;
            }

            card.innerHTML = `
                <div class="card-media">${mediaHtml}</div>
                <div class="card-content">
                    <div class="card-title" title="${item.name}">${item.name}</div>
                    <div class="card-tags">
                        ${item.tags.signal.map(t => `<span class="tag signal">${t}</span>`).join('')}
                        ${item.tags.time.map(t => `<span class="tag time">${t}</span>`).join('')}
                        ${item.tags.analysis.map(t => `<span class="tag analysis">${t}</span>`).join('')}
                        <span class="tag">${item.type.toUpperCase()}</span>
                    </div>
                </div>
            `;
            
            card.onclick = () => openModal(item);
            galleryGrid.appendChild(card);
        });

        resultsCount.textContent = `Showing ${filtered.length} of ${galleryData.length} items`;
    }

    searchInput.oninput = renderGallery;

    resetBtn.onclick = () => {
        Object.keys(filters).forEach(k => filters[k].clear());
        document.querySelectorAll('.filter-chip').forEach(el => el.classList.remove('active'));
        searchInput.value = '';
        renderGallery();
    };

    // Modal logic
    const modal = document.getElementById('modal');
    const modalIframe = document.getElementById('modal-iframe');
    const modalImg = document.getElementById('modal-img');
    const modalCaption = document.getElementById('modal-caption');
    const closeBtn = document.querySelector('.close');

    function openModal(item) {
        modal.style.display = 'block';
        modalCaption.textContent = item.name;
        
        if (item.type === 'html' || item.type === 'pdf') {
            modalIframe.src = item.rel_path;
            modalIframe.style.display = 'block';
            modalImg.style.display = 'none';
        } else {
            modalImg.src = item.rel_path;
            modalImg.style.display = 'block';
            modalIframe.style.display = 'none';
            modalIframe.src = '';
        }
    }

    closeBtn.onclick = () => {
        modal.style.display = 'none';
        modalIframe.src = '';
    };

    window.onclick = (event) => {
        if (event.target == modal) {
            modal.style.display = 'none';
            modalIframe.src = '';
        }
    };
});
