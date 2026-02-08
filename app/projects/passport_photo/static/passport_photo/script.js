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
            guides: true,
            center: true,
            highlight: false,
            background: false,
            autoCropArea: 0.8,
            ready() {
                // Potential place to add custom guides if needed
            }
        });
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

        // 3. Tile 6 photos (2 columns, 3 rows)
        // Each photo is 600x600. 
        // 2 cols * 600 = 1200px (full width)
        // 3 rows * 600 = 1800px (full height)
        
        // We'll add a tiny margin for cut lines if we want, but let's do 6 photos first
        for (let row = 0; row < 3; row++) {
            for (let col = 0; col < 2; col++) {
                const x = col * 600;
                const y = row * 600;
                ctx.drawImage(croppedCanvas, x, y, 600, 600);
                
                // Draw light cut lines
                ctx.strokeStyle = '#E2E8F0';
                ctx.lineWidth = 1;
                ctx.strokeRect(x, y, 600, 600);
            }
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
