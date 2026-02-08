document.addEventListener('DOMContentLoaded', function() {
    // Elements
    const uploadSection = document.getElementById('passport-photo-upload-section');
    const fileInput = document.getElementById('passport-photo-file-input');
    const editorSection = document.getElementById('passport-photo-editor-section');
    const imageElement = document.getElementById('passport-photo-image');
    const whitenBtn = document.getElementById('passport-photo-whiten-btn');
    const generateBtn = document.getElementById('passport-photo-generate-btn');
    const previewSection = document.getElementById('passport-photo-preview-section');
    const printCanvas = document.getElementById('passport-photo-print-canvas');
    const downloadBtn = document.getElementById('passport-photo-download-btn');
    const resetBtn = document.getElementById('passport-photo-reset-btn');
    const undoBtn = document.getElementById('passport-photo-undo-btn');
    const brightnessInput = document.getElementById('passport-photo-brightness');
    const brightnessValue = document.getElementById('passport-photo-brightness-value');
    const contrastInput = document.getElementById('passport-photo-contrast');
    const contrastValue = document.getElementById('passport-photo-contrast-value');

    let cropper = null;
    let selfieSegmentation = null;
    let originalImageDataUrl = null;

    // Apply Adjustments to UI
    function applyAdjustments() {
        const brightness = brightnessInput.value;
        const contrast = contrastInput.value;
        
        brightnessValue.innerText = `${brightness}%`;
        contrastValue.innerText = `${contrast}%`;
        
        // Apply filter to the cropper container for preview
        const container = document.querySelector('.cropper-container');
        if (container) {
            container.style.filter = `brightness(${brightness}%) contrast(${contrast}%)`;
        }
    }

    brightnessInput.addEventListener('input', applyAdjustments);
    contrastInput.addEventListener('input', applyAdjustments);

    // Initialize MediaPipe
    function initSegmentation() {
        if (selfieSegmentation) return;
        
        selfieSegmentation = new SelfieSegmentation({
            locateFile: (file) => {
                return `https://cdn.jsdelivr.net/npm/@mediapipe/selfie_segmentation/${file}`;
            }
        });

        selfieSegmentation.setOptions({
            modelSelection: 1, // 1 for landscape/better detail
        });

        selfieSegmentation.onResults(onSegmentationResults);
    }

    let segmentationResolve = null;
    function onSegmentationResults(results) {
        if (segmentationResolve) {
            segmentationResolve(results);
        }
    }

    async function whitenImageBackground(inputCanvas) {
        initSegmentation();
        
        return new Promise((resolve) => {
            segmentationResolve = async (results) => {
                const canvas = document.createElement('canvas');
                canvas.width = inputCanvas.width;
                canvas.height = inputCanvas.height;
                const ctx = canvas.getContext('2d');

                // Draw the mask directly (Very first version approach)
                ctx.save();
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                ctx.drawImage(results.segmentationMask, 0, 0, canvas.width, canvas.height);

                // Use the mask to draw the original image
                ctx.globalCompositeOperation = 'source-in';
                ctx.drawImage(results.image, 0, 0, canvas.width, canvas.height);

                // Fill the background with white
                ctx.globalCompositeOperation = 'destination-over';
                ctx.fillStyle = '#FFFFFF';
                ctx.fillRect(0, 0, canvas.width, canvas.height);
                ctx.restore();

                resolve(canvas.toDataURL('image/jpeg', 0.95));
            };

            selfieSegmentation.send({image: inputCanvas});
        });
    }

    // Whiten Background Button
    whitenBtn.addEventListener('click', async () => {
        if (!cropper) return;
        
        // Save original on first run
        if (!originalImageDataUrl) {
            originalImageDataUrl = imageElement.src;
        }

        const originalText = whitenBtn.innerText;
        whitenBtn.innerText = 'Processing...';
        whitenBtn.disabled = true;

        try {
            const tempCanvas = document.createElement('canvas');
            const img = new Image();
            img.src = originalImageDataUrl; // Always work from the true original
            
            await new Promise(r => img.onload = r);
            
            tempCanvas.width = img.width;
            tempCanvas.height = img.height;
            const ctx = tempCanvas.getContext('2d');
            ctx.drawImage(img, 0, 0);

            const whitenedDataUrl = await whitenImageBackground(tempCanvas);
            
            const cropData = cropper.getData();
            imageElement.src = whitenedDataUrl;
            
            setTimeout(() => {
                initCropper();
                setTimeout(() => {
                    if (cropper) cropper.setData(cropData);
                    undoBtn.classList.remove('passport-photo-hidden');
                }, 100);
            }, 50);

        } catch (err) {
            console.error('Segmentation error:', err);
            alert('Failed to whiten background.');
        } finally {
            whitenBtn.innerText = originalText;
            whitenBtn.disabled = false;
        }
    });

    // Undo Button
    undoBtn.addEventListener('click', () => {
        if (!originalImageDataUrl) return;
        
        const cropData = cropper.getData();
        imageElement.src = originalImageDataUrl;
        
        setTimeout(() => {
            initCropper();
            setTimeout(() => {
                if (cropper) cropper.setData(cropData);
                undoBtn.classList.add('passport-photo-hidden');
            }, 100);
        }, 50);
    });

    // Handle Upload
    const selectBtn = document.querySelector('.passport-photo-upload-section .passport-photo-btn-primary');
    const triggerUpload = () => fileInput.click();
    
    uploadSection.addEventListener('click', triggerUpload);
    if (selectBtn) {
        selectBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            triggerUpload();
        });
    }

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

        // 1.5 Apply brightness/contrast to the cropped result
        const brightness = brightnessInput.value;
        const contrast = contrastInput.value;
        if (brightness !== "100" || contrast !== "100") {
            const tempCanvas = document.createElement('canvas');
            tempCanvas.width = 600;
            tempCanvas.height = 600;
            const tempCtx = tempCanvas.getContext('2d');
            tempCtx.filter = `brightness(${brightness}%) contrast(${contrast}%)`;
            tempCtx.drawImage(croppedCanvas, 0, 0);
            
            // Swap out the canvas
            croppedCanvas.width = 600;
            croppedCanvas.height = 600;
            const ctx2 = croppedCanvas.getContext('2d');
            ctx2.drawImage(tempCanvas, 0, 0);
        }

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
        originalImageDataUrl = null;
        undoBtn.classList.add('passport-photo-hidden');
        
        // Reset adjustments
        brightnessInput.value = 100;
        contrastInput.value = 100;
        brightnessValue.innerText = '100%';
        contrastValue.innerText = '100%';
        
        if (cropper) {
            cropper.destroy();
            cropper = null;
        }
    });
});
