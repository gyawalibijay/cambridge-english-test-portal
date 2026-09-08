/* B1 READY ADVANCED ADMIN V33.3 */
(() => {
  'use strict';

  const escapeHtml = (value) => String(value || '').replace(/[&<>"']/g, c => ({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  }[c]));

  const kindFromName = (name) => {
    const ext = (String(name).toLowerCase().match(/\.[a-z0-9]+$/) || [''])[0];
    if (['.mp3','.wav','.m4a','.ogg','.aac','.flac','.webm'].includes(ext)) return 'audio';
    if (['.mp4','.mov','.m4v','.avi','.mkv'].includes(ext)) return 'video';
    if (['.jpg','.jpeg','.png','.gif','.webp','.svg','.avif'].includes(ext)) return 'image';
    if (['.pdf','.doc','.docx','.ppt','.pptx','.xls','.xlsx','.txt','.csv','.zip'].includes(ext)) return 'document';
    return 'file';
  };

  const previewMarkup = (kind, url, name) => {
    if (!url) return '';
    if (kind === 'image') return `<div class="b1-file-preview"><img src="${escapeHtml(url)}" alt=""><a href="${escapeHtml(url)}" target="_blank" rel="noopener">${escapeHtml(name)}</a></div>`;
    if (kind === 'audio') return `<div class="b1-file-preview"><audio controls preload="none" src="${escapeHtml(url)}"></audio><a href="${escapeHtml(url)}" target="_blank" rel="noopener">Open audio ↗</a></div>`;
    if (kind === 'video') return `<div class="b1-file-preview"><video controls preload="metadata" src="${escapeHtml(url)}"></video><a href="${escapeHtml(url)}" target="_blank" rel="noopener">Open video ↗</a></div>`;
    return `<div class="b1-file-preview"><span class="b1-file-chip">${escapeHtml(kind.toUpperCase())}</span><a href="${escapeHtml(url)}" target="_blank" rel="noopener">${escapeHtml(name)}</a></div>`;
  };

  const tuneFileInput = (input) => {
    if (input.dataset.b1Enhanced === '1') return;
    input.dataset.b1Enhanced = '1';

    const row = input.closest('.form-row') || input.parentElement;
    if (!row) return;

    const fieldHint = `${input.name} ${input.id} ${row.textContent}`.toLowerCase();
    if (fieldHint.includes('audio')) input.accept = input.accept || 'audio/*,.mp3,.wav,.m4a,.ogg,.webm,.aac';
    else if (fieldHint.includes('video')) input.accept = input.accept || 'video/*,.mp4,.webm,.mov,.m4v';
    else if (fieldHint.includes('image') || fieldHint.includes('photo')) input.accept = input.accept || 'image/*,.jpg,.jpeg,.png,.webp,.gif,.avif';
    else if (fieldHint.includes('document') || fieldHint.includes('material') || fieldHint.includes('file')) input.accept = input.accept || '.pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.txt,.csv,.zip,audio/*,video/*,image/*';

    const shell = document.createElement('div');
    shell.className = 'b1-file-drop';
    input.parentNode.insertBefore(shell, input);
    shell.appendChild(input);

    const help = document.createElement('div');
    help.className = 'b1-file-help';
    help.textContent = 'Choose a file or drag it here. Existing Django upload rules and permissions remain unchanged.';
    shell.appendChild(help);

    const existing = row.querySelector('.file-upload a');
    if (existing && existing.href && !row.querySelector('.b1-file-preview')) {
      const k = kindFromName(existing.href);
      shell.insertAdjacentHTML('beforeend', previewMarkup(k, existing.href, existing.textContent.trim() || existing.href));
    }

    const renderSelected = () => {
      shell.querySelectorAll('.b1-selected-preview').forEach(n => n.remove());
      const file = input.files && input.files[0];
      if (!file) return;

      const wrap = document.createElement('div');
      wrap.className = 'b1-selected-preview';
      const sizeMb = file.size / (1024 * 1024);
      const kind = kindFromName(file.name);
      let body = `<div class="b1-file-preview"><span class="b1-file-chip">${escapeHtml(kind.toUpperCase())}</span><div><strong style="font-size:9px">${escapeHtml(file.name)}</strong><div class="b1-file-help">${sizeMb.toFixed(1)} MB · ready to upload when you save</div></div></div>`;

      if (['image','audio','video'].includes(kind)) {
        const url = URL.createObjectURL(file);
        body = previewMarkup(kind, url, file.name);
      }
      wrap.innerHTML = body;
      shell.appendChild(wrap);
    };

    input.addEventListener('change', renderSelected);

    ['dragenter','dragover'].forEach(type => shell.addEventListener(type, e => {
      e.preventDefault();
      shell.classList.add('is-dragging');
    }));
    ['dragleave','drop'].forEach(type => shell.addEventListener(type, e => {
      e.preventDefault();
      shell.classList.remove('is-dragging');
    }));
    shell.addEventListener('drop', e => {
      const files = e.dataTransfer && e.dataTransfer.files;
      if (!files || !files.length) return;
      try {
        const dt = new DataTransfer();
        dt.items.add(files[0]);
        input.files = dt.files;
        renderSelected();
      } catch (_) {}
    });
  };

  const initFileInputs = () => {
    document.querySelectorAll('input[type="file"]').forEach(tuneFileInput);
  };

  const initModuleSearch = () => {
    const input = document.getElementById('b1-admin-module-search');
    if (!input) return;
    const modules = [...document.querySelectorAll('.b1-admin-models .module')];
    input.addEventListener('input', () => {
      const q = input.value.trim().toLowerCase();
      modules.forEach(module => {
        module.classList.toggle('b1-search-hidden', !!q && !module.textContent.toLowerCase().includes(q));
      });
    });
  };

  const initSaveProtection = () => {
    document.querySelectorAll('.submit-row input[type="submit"]').forEach(btn => {
      btn.addEventListener('click', () => {
        btn.dataset.originalValue = btn.value;
        setTimeout(() => {
          if (!btn.disabled) return;
          btn.value = 'Saving…';
        }, 0);
      });
    });
  };

  document.addEventListener('DOMContentLoaded', () => {
    initFileInputs();
    initModuleSearch();
    initSaveProtection();
  });
})();
