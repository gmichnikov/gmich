/**
 * Travel Log — Photo upload for entry edit page.
 * Compress image, get presigned URL, PUT to R2, confirm. Append new photos to DOM.
 * Remove button uses form POST (with CSRF) for existing photos; fetch for dynamically added.
 */
(function () {
  const section = document.getElementById('tlog-photos-section');
  const grid = document.getElementById('tlog-photos-grid');
  const fileInput = document.getElementById('tlog-photo-input');
  if (!section || !grid || !fileInput) return;

  const entryId = parseInt(section.getAttribute('data-entry-id'), 10);
  const csrfToken = section.getAttribute('data-csrf-token') ||
    document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');

  const MAX_EDGE = 1200;
  const JPEG_QUALITY = 0.8;

  function showStatus(msg, isError) {
    let el = document.getElementById('tlog-photo-upload-status');
    if (!el) {
      el = document.createElement('p');
      el.id = 'tlog-photo-upload-status';
      el.className = 'tlog-photo-upload-status';
      section.appendChild(el);
    }
    el.textContent = msg || '';
    el.className = 'tlog-photo-upload-status' + (isError ? ' tlog-photo-upload-status-error' : '');
    el.style.display = msg ? 'block' : 'none';
  }

  function compressImage(file) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => {
        const canvas = document.createElement('canvas');
        let w = img.width;
        let h = img.height;
        if (w > MAX_EDGE || h > MAX_EDGE) {
          if (w > h) {
            h = (h * MAX_EDGE) / w;
            w = MAX_EDGE;
          } else {
            w = (w * MAX_EDGE) / h;
            h = MAX_EDGE;
          }
        }
        canvas.width = w;
        canvas.height = h;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0, w, h);
        canvas.toBlob(
          (blob) => resolve(blob || new Blob()),
          'image/jpeg',
          JPEG_QUALITY
        );
      };
      img.onerror = () => reject(new Error('Failed to load image'));
      img.src = URL.createObjectURL(file);
    });
  }

  function appendPhotoToGrid(photoId, viewUrl) {
    const item = document.createElement('div');
    item.className = 'tlog-photo-item';
    item.setAttribute('data-photo-id', photoId);
    const deleteUrl = `/travel-log/entries/${entryId}/photos/${photoId}/delete`;
    item.innerHTML = `
      <img src="${viewUrl.replace(/"/g, '&quot;')}" alt="Photo" class="tlog-photo-img" loading="lazy">
      <form method="post" action="${deleteUrl.replace(/"/g, '&quot;')}" class="tlog-photo-remove-form">
        <input type="hidden" name="csrf_token" value="${(csrfToken || '').replace(/"/g, '&quot;')}">
        <button type="submit" class="tlog-photo-remove-btn">Remove</button>
      </form>
    `;
    grid.appendChild(item);
  }

  async function uploadFile(file) {
    showStatus('Uploading...', false);
    try {
      const blob = await compressImage(file);

      let presignRes, presignData;
      try {
        presignRes = await fetch('/travel-log/api/photos/presign', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken || '',
          },
          body: JSON.stringify({ entry_id: entryId }),
        });
        presignData = await presignRes.json();
      } catch (e) {
        throw new Error('Could not reach server (check R2 config). ' + (e.message || ''));
      }
      if (!presignRes.ok || !presignData.upload_url || !presignData.key) {
        throw new Error(presignData.error || 'Failed to get upload URL');
      }

      let putRes;
      try {
        putRes = await fetch(presignData.upload_url, {
          method: 'PUT',
          body: blob,
          headers: { 'Content-Type': 'image/jpeg' },
        });
      } catch (e) {
        throw new Error(
          'Upload to storage failed. Add CORS to your R2 bucket: Cloudflare R2 → bucket → Settings → CORS policy. ' +
          'Allow PUT from your app origin (e.g. http://localhost:5518). See PLAN.md for full config.'
        );
      }
      if (!putRes.ok) {
        throw new Error('Upload failed (' + putRes.status + ')');
      }

      const confirmRes = await fetch('/travel-log/api/photos/confirm', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken || '',
        },
        body: JSON.stringify({
          entry_id: entryId,
          key: presignData.key,
        }),
      });
      const confirmData = await confirmRes.json();
      if (!confirmRes.ok || !confirmData.success) {
        throw new Error(confirmData.error || 'Failed to save photo');
      }

      appendPhotoToGrid(confirmData.photo_id, confirmData.view_url || '');
      showStatus('');
    } catch (e) {
      showStatus(e.message || 'Upload failed. Please try again.', true);
    }
  }

  fileInput.addEventListener('change', async function () {
    const files = Array.from(this.files || []);
    this.value = '';
    for (const file of files) {
      if (!file.type.startsWith('image/')) continue;
      await uploadFile(file);
    }
  });

  section.addEventListener('submit', function (e) {
    if (e.target.classList.contains('tlog-photo-remove-form')) {
      if (!confirm('Are you sure you want to remove this photo?')) {
        e.preventDefault();
      }
    }
  });

  /* Lightbox: click photo to view larger */
  function getPhotoUrls() {
    return Array.from(grid.querySelectorAll('.tlog-photo-item .tlog-photo-img'))
      .map(img => img.src)
      .filter(Boolean);
  }

  function openLightbox(imgSrc, index) {
    const urls = getPhotoUrls();
    const idx = index >= 0 ? index : urls.indexOf(imgSrc);
    if (idx < 0) return;

    const overlay = document.createElement('div');
    overlay.className = 'tlog-lightbox-overlay';
    overlay.setAttribute('aria-hidden', 'false');
    overlay.innerHTML = `
      <button type="button" class="tlog-lightbox-close" aria-label="Close">×</button>
      ${urls.length > 1 ? `
        <button type="button" class="tlog-lightbox-prev" aria-label="Previous">‹</button>
        <button type="button" class="tlog-lightbox-next" aria-label="Next">›</button>
      ` : ''}
      <div class="tlog-lightbox-content">
        <img src="${urls[idx].replace(/"/g, '&quot;')}" alt="Photo" class="tlog-lightbox-img">
      </div>
      ${urls.length > 1 ? `<span class="tlog-lightbox-counter">${idx + 1} / ${urls.length}</span>` : ''}
    `;

    let currentIdx = idx;
    const lightboxImg = overlay.querySelector('.tlog-lightbox-img');
    const counterEl = overlay.querySelector('.tlog-lightbox-counter');

    function showPhoto(i) {
      currentIdx = ((i % urls.length) + urls.length) % urls.length;
      lightboxImg.src = urls[currentIdx];
      if (counterEl) counterEl.textContent = `${currentIdx + 1} / ${urls.length}`;
    }

    function close() {
      overlay.remove();
      overlay.setAttribute('aria-hidden', 'true');
      document.body.classList.remove('tlog-lightbox-open');
      document.removeEventListener('keydown', onKeydown);
    }

    function onKeydown(e) {
      if (e.key === 'Escape') close();
      if (urls.length > 1 && e.key === 'ArrowLeft') showPhoto(currentIdx - 1);
      if (urls.length > 1 && e.key === 'ArrowRight') showPhoto(currentIdx + 1);
    }

    overlay.querySelector('.tlog-lightbox-close').addEventListener('click', close);
    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) close();
    });
    if (urls.length > 1) {
      overlay.querySelector('.tlog-lightbox-prev').addEventListener('click', function (e) {
        e.stopPropagation();
        showPhoto(currentIdx - 1);
      });
      overlay.querySelector('.tlog-lightbox-next').addEventListener('click', function (e) {
        e.stopPropagation();
        showPhoto(currentIdx + 1);
      });
    }
    document.addEventListener('keydown', onKeydown);
    document.body.classList.add('tlog-lightbox-open');
    document.body.appendChild(overlay);
  }

  grid.addEventListener('click', function (e) {
    if (e.target.closest('.tlog-photo-remove-form')) return;
    if (e.target.classList.contains('tlog-photo-img')) {
      e.preventDefault();
      openLightbox(e.target.src, -1);
    }
  });
})();
