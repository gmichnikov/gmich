document.addEventListener('DOMContentLoaded', function() {
    // Elements
    const uploadSection = document.getElementById('passport-photo-upload-section');
    const fileInput = document.getElementById('passport-photo-file-input');
    const editorSection = document.getElementById('passport-photo-editor-section');
    const imageElement = document.getElementById('passport-photo-image');
    const generateBtn = document.getElementById('passport-photo-generate-btn');
    const previewSection = document.getElementById('passport-photo-preview-section');
    const printCanvas = document.getElementById('passport-photo-print-canvas');
    const downloadBtn = document.getElementById('passport-photo-download-btn');
    const resetBtn = document.getElementById('passport-photo-reset-btn');

    let cropper = null;

    // Handle Upload
    uploadSection.addEventListener('click', () => fileInput.click());

    uploadSection.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadSection.classList.add('dragover');
    });

    uploadSection.addEventListener('dragleave', () => {
        uploadSection.classList.remove('dragover');
    });

    uploadSection.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadSection.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) {
            handleFile(e.dataTransfer.files[0]);
        }
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFile(e.target.files[0]);
        }
    });

    function handleFile(file) {
        if (!file.type.startsWith('image/')) {
            alert('Please upload an image file (JPEG or PNG).');
            return;
        }

        const reader = new FileReader();
        reader.onload = (e) => {
            imageElement.src = e.target.result;
            initCropper();
        };
        reader.readAsDataURL(file);
    }

    function initCropper() {
        if (cropper) {
            cropper.destroy();
        }

        uploadSection.classList.add('passport-photo-hidden');
        editorSection.style.display = 'block';

        cropper = new Cropper(imageElement, {
            aspectRatio: 1, // 1:1 square for passport
            viewMode: 1,
            guides: false, // Turn off default cropper guides to reduce clutter
            center: false,
            highlight: false,
            background: false,
            autoCropArea: 0.8,
            ready() {
                injectGuide();
            }
        });
    }

    function injectGuide() {
        const viewBox = document.querySelector('.cropper-view-box');
        if (!viewBox) return;

        // Create a container for our guide
        const guideContainer = document.createElement('div');
        guideContainer.className = 'passport-photo-cropper-guide';
        
        // Use the same SVG as before but simplified for injection
        guideContainer.innerHTML = `
            <svg viewBox="0 0 100 100" preserveAspectRatio="xMidYMid meet" style="width: 100%; height: 100%; position: absolute; top: 0; left: 0;">
                <!-- Head outline -->
                <path d="M50,15 C35,15 25,25 25,40 C25,52 30,62 40,65 L40,75 L60,75 L60,65 C70,62 75,52 75,40 C75,25 65,15 50,15 Z" 
                      fill="none" stroke="#00d2ff" stroke-width="0.8" stroke-dasharray="2,1" />
                <!-- Subtle dark outline for visibility on light backgrounds -->
                <path d="M50,15 C35,15 25,25 25,40 C25,52 30,62 40,65 L40,75 L60,75 L60,65 C70,62 75,52 75,40 C75,25 65,15 50,15 Z" 
                      fill="none" stroke="rgba(0,0,0,0.3)" stroke-width="0.2" style="transform: scale(1.02); transform-origin: center;" />
                
                <!-- Ears -->
                <path d="M25,35 C22,35 20,38 20,42 C20,46 22,48 25,48" fill="none" stroke="#00d2ff" stroke-width="0.5" stroke-dasharray="2,1" />
                <path d="M75,35 C78,35 80,38 80,42 C80,46 78,48 75,48" fill="none" stroke="#00d2ff" stroke-width="0.5" stroke-dasharray="2,1" />
                
                <!-- Eyes guide line -->
                <line x1="30" y1="40" x2="70" y2="40" stroke="#00d2ff" stroke-width="0.4" stroke-dasharray="1,1" />
                
                <!-- Text Labels -->
                <text x="50" y="11" text-anchor="middle" fill="#00d2ff" font-size="4" font-weight="bold" style="paint-order: stroke; stroke: rgba(0,0,0,0.5); stroke-width: 0.5px;">TOP OF HEAD</text>
                <text x="50" y="73" text-anchor="middle" fill="#00d2ff" font-size="4" font-weight="bold" style="paint-order: stroke; stroke: rgba(0,0,0,0.5); stroke-width: 0.5px;">CHIN</text>
                
                <!-- Shoulders -->
                <path d="M10,95 C10,85 25,75 50,75 C75,75 90,85 90,95" 
                      fill="none" stroke="#00d2ff" stroke-width="0.6" stroke-dasharray="2,1" />
            </svg>
        `;
        
        viewBox.appendChild(guideContainer);
    }

    // Generate Print Sheet
    generateBtn.addEventListener('click', () => {
        if (!cropper) return;

        // 1. Get cropped image (600x600 for 2x2 at 300dpi)
        const croppedCanvas = cropper.getCroppedCanvas({
            width: 600,
            height: 600,
            imageSmoothingEnabled: true,
            imageSmoothingQuality: 'high',
        });

        // 2. Setup 4x6 print canvas (1200x1800 for 300dpi)
        // Orientation: 4" wide (1200px) x 6" high (1800px)
        const ctx = printCanvas.getContext('2d');
        printCanvas.width = 1200;
        printCanvas.height = 1800;

        // Fill with white background
        ctx.fillStyle = '#FFFFFF';
        ctx.fillRect(0, 0, printCanvas.width, printCanvas.height);

        // 3. Tile 2 photos (1 column, 2 rows) centered
        // Each photo is 600x600. 
        // 1 col * 600 = 600px. Margin = (1200 - 600) / 2 = 300px
        // 2 rows * 600 = 1200px. Margin = (1800 - 1200) / 2 = 300px
        
        const startX = 300;
        const startY = 300;
        
        for (let row = 0; row < 2; row++) {
            const x = startX;
            const y = startY + (row * 600);
            ctx.drawImage(croppedCanvas, x, y, 600, 600);
            
            // Draw light cut lines
            ctx.strokeStyle = '#E2E8F0';
            ctx.lineWidth = 1;
            ctx.strokeRect(x, y, 600, 600);
        }

        // Show preview
        previewSection.style.display = 'block';
        previewSection.scrollIntoView({ behavior: 'smooth' });
    });

    // Download
    downloadBtn.addEventListener('click', () => {
        const link = document.createElement('a');
        link.download = 'passport-photos-4x6-print-sheet.jpg';
        link.href = printCanvas.toDataURL('image/jpeg', 0.95);
        link.click();
    });

    // Reset
    resetBtn.addEventListener('click', () => {
        editorSection.style.display = 'none';
        previewSection.style.display = 'none';
        uploadSection.classList.remove('passport-photo-hidden');
        fileInput.value = '';
        if (cropper) {
            cropper.destroy();
            cropper = null;
        }
    });
});
