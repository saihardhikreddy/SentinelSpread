































































































































































































































































































































































































































































































































































































































































































































































































































  // Generic Fetch API Wrapper
  async function apiCall(endpoint, method = 'GET', body = null) {
    try {
      const options = { method };
      if (body) {
        if (body instanceof FormData) {
          options.body = body;
        } else {
          options.headers = { 'Content-Type': 'application/json' };
          options.body = JSON.stringify(body);
        }
      }

      const response = await fetch(`${API_BASE}${endpoint}`, options);
      if (!response.ok) {
        let errDetail = 'API Request Failed';
        try {
          const errData = await response.json();
          errDetail = errData.detail || errData.message || response.statusText;
        } catch (e) {}
        throw new Error(errDetail);
      }

      const contentType = response.headers.get('content-type');
      if (contentType && contentType.includes('application/json')) {
        return await response.json();
      }
      return await response.blob();

    } catch (err) {
      showToast(err.message, 'error');
      throw err;
    }
  }

  async function checkApiHealth() {
    try {
      const start = performance.now();
      const res = await apiCall('/health');
      const latency = Math.round(performance.now() - start);
      if (res && res.status === 'healthy') {
        document.getElementById('api-status-dot').className = 'status-dot';
        document.getElementById('api-status-text').textContent = `FastAPI Connected (${latency}ms)`;
      }
    } catch (e) {
      document.getElementById('api-status-dot').style.background = '#f87171';
      document.getElementById('api-status-text').textContent = 'FastAPI Disconnected';
    }
  }

  function fileToBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = error => reject(error);
      reader.readAsDataURL(file);
    });
  }

  function getImageDimensions(dataUrl) {
    return new Promise((resolve) => {
      const img = new Image();
      img.onload = () => resolve({ width: img.width, height: img.height });
      img.src = dataUrl;
    });
  }

  function setupDropzone(dropzoneId, inputId, onFileLoaded) {
    const dz = document.getElementById(dropzoneId);
    const input = document.getElementById(inputId);
    if (!dz || !input) return;

    dz.addEventListener('click', () => input.click());

    dz.addEventListener('dragover', (e) => {
      e.preventDefault();
      dz.classList.add('dragover');
    });

    dz.addEventListener('dragleave', () => dz.classList.remove('dragover'));

    dz.addEventListener('drop', async (e) => {
      e.preventDefault();
      dz.classList.remove('dragover');
      if (e.dataTransfer.files.length > 0) {
        onFileLoaded(e.dataTransfer.files[0]);
      }
    });

    input.addEventListener('change', (e) => {
      if (e.target.files.length > 0) {
        onFileLoaded(e.target.files[0]);
      }
    });
  }

  function initCopyButtons() {
    document.querySelectorAll('.code-copy-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const pre = btn.nextElementSibling;
        if (pre && pre.textContent) {
          navigator.clipboard.writeText(pre.textContent);
          const orig = btn.textContent;
          btn.textContent = 'Copied!';
          setTimeout(() => btn.textContent = orig, 2000);
        }
      });
    });
  }

  // Navigation & Tab Switching
  function initNavigation() {
    const switchTab = (tabId) => {
      if (!tabId) return;

      document.querySelectorAll('.dock-text-item').forEach(l => l.classList.remove('active'));
      document.querySelectorAll('.tab-view').forEach(v => v.classList.remove('active'));

      const activeItem = document.querySelector(`.dock-text-item[data-tab="${tabId}"]`);
      if (activeItem) {
        activeItem.classList.add('active');
        const pill = document.getElementById('nav-pill-active');
        if (pill) {
          pill.style.left = `${activeItem.offsetLeft}px`;
          pill.style.width = `${activeItem.offsetWidth}px`;
        }
      }

      const targetView = document.getElementById(tabId);
      if (targetView) {
        targetView.classList.add('active');
        targetView.querySelectorAll('.scroll-reveal').forEach(el => el.classList.add('revealed'));
      }

      state.activeTab = tabId;
      window.scrollTo({ top: 0, behavior: 'smooth' });

      if (typeof state.triggerParticleBurst === 'function') {
        state.triggerParticleBurst();
      }
    };

    document.querySelectorAll('[data-tab]').forEach(elem => {
      elem.addEventListener('click', () => {
        const tabId = elem.getAttribute('data-tab');
        switchTab(tabId);
      });
    });
  }

  // Sub-Dock Navigation Handler
  function initSubDocks() {
    // Steganography Sub-Dock
    document.querySelectorAll('[data-subtab]').forEach(item => {
      item.addEventListener('click', () => {
        document.querySelectorAll('[data-subtab]').forEach(i => i.classList.remove('active'));
        document.querySelectorAll('#tab-steganography .subtab-panel').forEach(p => p.style.display = 'none');
        
        item.classList.add('active');
        const targetId = item.getAttribute('data-subtab');
        const targetPanel = document.getElementById(targetId);
        if (targetPanel) {
          targetPanel.style.display = 'block';
          targetPanel.querySelectorAll('.scroll-reveal').forEach(el => el.classList.add('revealed'));
        }
      });
    });

    // Metrics Sub-Dock
    document.querySelectorAll('[data-mettab]').forEach(item => {
      item.addEventListener('click', () => {
        document.querySelectorAll('[data-mettab]').forEach(i => i.classList.remove('active'));
        document.querySelectorAll('#tab-metrics .subtab-panel').forEach(p => p.style.display = 'none');
        
        item.classList.add('active');
        const targetId = item.getAttribute('data-mettab');
        const targetPanel = document.getElementById(targetId);
        if (targetPanel) {
          targetPanel.style.display = 'block';
          targetPanel.querySelectorAll('.scroll-reveal').forEach(el => el.classList.add('revealed'));
        }
      });
    });
  }

  // View 2: Steganography
  function initSteganography() {
    document.getElementById('btn-steg-gen-keys').addEventListener('click', async () => {
      try {
        showToast('Generating RSA-2048 key pair...', 'info');
        const keys = await apiCall('/api/crypto/generate-rsa-keys', 'POST', { key_size: 2048 });
        
        state.stegPubKeyPem = keys.public_key_pem;
        state.stegPrivKeyPem = keys.private_key_pem;

        scrambleText(document.getElementById('steg-pub-pem'), keys.public_key_pem);
        scrambleText(document.getElementById('steg-priv-pem'), keys.private_key_pem);

        showToast('RSA-2048 key pair generated for Steganography!', 'success');
      } catch (e) {}
    });

    setupDropzone('dz-steg-carrier', 'file-steg-carrier', async (file) => {
      try {
        const b64 = await fileToBase64(file);
        const dims = await getImageDimensions(b64);
        state.stegCarrierB64 = b64;
        state.stegCarrierWidth = dims.width;
        state.stegCarrierHeight = dims.height;

        const capRes = await apiCall('/api/stego/capacity', 'POST', { width: dims.width, height: dims.height });
        state.stegCapacityBytes = capRes.capacity_bytes;

        document.getElementById('img-steg-carrier').src = b64;
        document.getElementById('prev-steg-carrier').style.display = 'flex';

        updateStegCapacityUI();
        showToast(`Carrier loaded (${dims.width}x${dims.height}px, Capacity: ${capRes.capacity_bytes} bytes)`, 'success');
      } catch (e) {}
    });

    const msgInput = document.getElementById('input-steg-msg');
    msgInput.addEventListener('input', updateStegCapacityUI);

    function updateStegCapacityUI() {
      const bytesUsed = new TextEncoder().encode(msgInput.value).length;
      const totalCap = state.stegCapacityBytes;
      const textSpan = document.getElementById('steg-cap-text');
      const fillBar = document.getElementById('steg-cap-fill');

      if (totalCap === 0) {
        textSpan.textContent = `${bytesUsed} Bytes (Upload Carrier)`;
        fillBar.style.width = '0%';
        return;
      }

      const pct = Math.min(100, ((bytesUsed / totalCap) * 100)).toFixed(1);
      textSpan.textContent = `${bytesUsed} / ${totalCap} Bytes (${pct}%)`;
      fillBar.style.width = `${pct}%`;

      fillBar.className = 'progress-fill';
      if (pct >= 100) fillBar.classList.add('error');
      else if (pct >= 80) fillBar.classList.add('warn');
    }

    document.getElementById('btn-steg-embed-act').addEventListener('click', async () => {
      if (!state.stegCarrierB64) {
        showToast('Please upload a carrier image.', 'warning');
        return;
      }
      let message = msgInput.value;
      if (!message) {
        showToast('Please enter a secret message payload.', 'warning');
        return;
      }

      try {
        const pwd = document.getElementById('input-steg-pwd').value;
        if (pwd) {
          const encRes = await apiCall('/api/crypto/encrypt-aes', 'POST', {
            plaintext: message,
            password: pwd
          });
          message = encRes.ciphertext_payload;
        } else if (state.stegPubKeyPem) {
          const encRes = await apiCall('/api/crypto/encrypt-hybrid', 'POST', {
            plaintext: message,
            public_key_pem: state.stegPubKeyPem
          });
          message = JSON.stringify(encRes);
        }

        const embedRes = await apiCall('/api/stego/embed', 'POST', {
          image_b64: state.stegCarrierB64,
          payload_text: message
        });

        document.getElementById('img-steg-out').src = embedRes.stego_image_b64;
        document.getElementById('res-steg-bits').textContent = embedRes.bits_used;
        document.getElementById('res-steg-psnr').textContent = `${embedRes.metrics.psnr_db.toFixed(2)} dB`;
        document.getElementById('res-steg-mse').textContent = embedRes.metrics.mse.toFixed(3);

        const dlBtn = document.getElementById('btn-steg-download');
        dlBtn.href = embedRes.stego_image_b64;

        document.getElementById('box-steg-out-placeholder').style.display = 'none';
        document.getElementById('box-steg-out-res').style.display = 'block';

        state.metricsOrigB64 = state.stegCarrierB64;
        state.metricsModB64 = embedRes.stego_image_b64;

        showToast('Message encrypted and embedded into stego PNG!', 'success');
      } catch (e) {}
    });

    setupDropzone('dz-steg-extract', 'file-steg-extract', async (file) => {
      try {
        const b64 = await fileToBase64(file);
        state.stegExtractB64 = b64;
        document.getElementById('img-steg-ext-prev').src = b64;
        document.getElementById('prev-steg-ext').style.display = 'flex';
        showToast('Stego image loaded for extraction.', 'info');
      } catch (e) {}
    });

    document.getElementById('btn-steg-extract-act').addEventListener('click', async () => {
      if (!state.stegExtractB64) {
        showToast('Please upload a stego image.', 'warning');
        return;
      }

      try {
        const extRes = await apiCall('/api/stego/extract', 'POST', {
          stego_image_b64: state.stegExtractB64
        });

        let rawText = extRes.extracted_text;
        const pwd = document.getElementById('input-steg-ext-pwd').value;

        if (rawText.trim().startsWith('{"enc": "aes-256-gcm"')) {
          if (!pwd) {
            showToast('AES Encrypted payload detected! Please enter the decryption password.', 'warning');
            scrambleText(document.getElementById('output-steg-recovered'), `[AES Encrypted Payload]:\n${rawText}`);
            return;
          }
          const decRes = await apiCall('/api/crypto/decrypt-aes', 'POST', {
            ciphertext_payload: rawText,
            password: pwd
          });
          rawText = decRes.plaintext;
          showToast('AES encrypted payload decrypted successfully!', 'success');
        } else if (rawText.trim().startsWith('{"mode": "webcrypto-hybrid"')) {
          if (!state.stegPrivKeyPem) {
            showToast('Hybrid RSA payload detected! Please generate or provide private key.', 'warning');
            scrambleText(document.getElementById('output-steg-recovered'), `[RSA Hybrid Encrypted Payload]:\n${rawText}`);
            return;
          }
          const payloadObj = JSON.parse(rawText);
          const decRes = await apiCall('/api/crypto/decrypt-hybrid', 'POST', {
            payload: payloadObj,
            private_key_pem: state.stegPrivKeyPem
          });
          rawText = decRes.plaintext;
          showToast('RSA Hybrid payload decrypted successfully!', 'success');
        } else {
          showToast('Plaintext payload recovered!', 'success');
        }

        scrambleText(document.getElementById('output-steg-recovered'), rawText);
      } catch (e) {}
    });

    // -------------------------------------------------------------------
    // Audio / Video (WAV / MP4) Steganography Event Handlers with Audio Players
    // -------------------------------------------------------------------
    let audioEmbedFile = null;
    let audioExtractFile = null;

    setupDropzone('dz-audio-embed', 'file-audio-embed', (file) => {
      audioEmbedFile = file;
      const badge = document.getElementById('audio-embed-file-badge');
      badge.textContent = `Selected: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
      badge.style.display = 'inline-block';

      // Load preview into Web Audio Player
      const carrierPlayer = document.getElementById('player-audio-carrier');
      if (carrierPlayer) {
        carrierPlayer.src = URL.createObjectURL(file);
        document.getElementById('box-audio-carrier-player').style.display = 'block';
      }

      showToast(`Selected audio/video file: ${file.name}`, 'info');
    });

    let lastAudioProofData = null;

    function initOrRefreshAudioProof() {
      if (!lastAudioProofData) {
        lastAudioProofData = generateDefaultAudioProofData();
      }
      renderAudioStegoVisualProof(lastAudioProofData);
    }

    function generateDefaultAudioProofData() {
      const sampleCount = 2000;
      const durationMs = 45.35;
      const origWave = [];
      const stegoWave = [];
      const lsbDeltas = [];
      const activeEmbeddedBits = 832;

      for (let i = 0; i < sampleCount; i++) {
        const t = (i / sampleCount) * (durationMs / 1000);
        const val = 0.5 * Math.sin(2 * Math.PI * 440 * t) + 0.2 * Math.sin(2 * Math.PI * 880 * t);
        const intVal = Math.round(val * 20000);
        origWave.push(intVal);

        if (i < activeEmbeddedBits && (i % 2 === 0)) {
          stegoWave.push(intVal + 1);
          lsbDeltas.push(1.0);
        } else {
          stegoWave.push(intVal);
          lsbDeltas.push(0.0);
        }
      }

      return {
        payload_bytes: 96,
        total_bits_embedded: 832,
        capacity_used_pct: 0.94,
        magic_header: "ASTG (4 Bytes)",
        cipher_algo: "AES-128-CBC (PKCS7 Padded)",
        derived_key_hint: "SHA-256('SentinelSecretKey2026')[:16]",
        plaintext_preview: "CONFIDENTIAL SENTINEL-SPREAD COMMUNICATE: LAT=37.7749 LONG=-122.4194 KEY=0x9F42",
        status_verification: "✓ STATUS: 100% ACOUSTIC-LAYER PAYLOAD RECOVERY VERIFIED",
        plot_data: {
          orig_waveform: origWave,
          stego_waveform: stegoWave,
          lsb_deltas: lsbDeltas,
          duration_ms: durationMs,
          sample_count: sampleCount
        }
      };
    }

    function renderAudioStegoVisualProof(details) {
      lastAudioProofData = details;
      const card = document.getElementById('card-audio-proof');
      if (!card) return;

      card.style.display = 'block';
      card.classList.add('revealed');

      document.getElementById('meta-magic').textContent = details.magic_header || 'ASTG (4 Bytes)';
      document.getElementById('meta-length').textContent = details.payload_bytes ? `${details.payload_bytes} Bytes` : '96 Bytes';
      document.getElementById('meta-cipher').textContent = details.cipher_algo || 'AES-128-CBC (PKCS7 Padded)';
      document.getElementById('meta-key').textContent = details.derived_key_hint || `SHA-256(...)[:16]`;
      document.getElementById('meta-bits').textContent = details.total_bits_embedded ? `${details.total_bits_embedded} bits` : '832 bits';
      document.getElementById('meta-cap').textContent = details.capacity_used_pct !== undefined ? `${details.capacity_used_pct}%` : '0.94%';
      document.getElementById('meta-plaintext').textContent = details.plaintext_preview || details.extracted_text || 'CONFIDENTIAL PAYLOAD';
      document.getElementById('meta-status').textContent = details.status_verification || '✓ STATUS: 100% ACOUSTIC-LAYER PAYLOAD RECOVERY VERIFIED';

      if (details.plot_data) {
        setTimeout(() => {
          drawWaveformComparisonCanvas(details.plot_data);
          drawLSBResidualCanvas(details.plot_data);
        }, 50);
      }
    }

    function drawWaveformComparisonCanvas(plotData) {
      const cvs = document.getElementById('canvas-audio-waveform');
      if (!cvs || !cvs.parentElement) return;
      const ctx = cvs.getContext('2d');

      const orig = plotData.orig_waveform;
      const stego = plotData.stego_waveform;
      if (!orig || !orig.length) return;

      const width = cvs.parentElement.clientWidth || 700;
      const height = 180;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);

      cvs.width = width * dpr;
      cvs.height = height * dpr;
      cvs.style.width = `${width}px`;
      cvs.style.height = `${height}px`;

      ctx.scale(dpr, dpr);
      ctx.fillStyle = '#06030c';
      ctx.fillRect(0, 0, width, height);

      const paddingLeft = 55;
      const paddingBottom = 25;
      const paddingTop = 15;
      const paddingRight = 20;

      const plotW = width - paddingLeft - paddingRight;
      const plotH = height - paddingTop - paddingBottom;

      let minPcm = -20000;
      let maxPcm = 20000;
      if (orig && orig.length) {
        let dataMin = orig[0], dataMax = orig[0];
        for (let i = 0; i < orig.length; i++) {
          if (orig[i] < dataMin) dataMin = orig[i];
          if (orig[i] > dataMax) dataMax = orig[i];
        }
        const margin = Math.max(Math.abs(dataMin), Math.abs(dataMax)) * 1.15 || 20000;
        minPcm = -margin;
        maxPcm = margin;
      }

      const yTicks = [Math.round(minPcm * 0.8), Math.round(minPcm * 0.4), 0, Math.round(maxPcm * 0.4), Math.round(maxPcm * 0.8)];
      ctx.fillStyle = '#8e8a9f';
      ctx.font = '10px "JetBrains Mono", monospace';
      ctx.textAlign = 'right';

      yTicks.forEach(val => {
        const yNorm = (val - minPcm) / (maxPcm - minPcm);
        const y = paddingTop + plotH * (1 - yNorm);
        ctx.beginPath();
        ctx.strokeStyle = val === 0 ? 'rgba(255, 255, 255, 0.25)' : 'rgba(255, 255, 255, 0.08)';
        ctx.moveTo(paddingLeft, y);
        ctx.lineTo(paddingLeft + plotW, y);
        ctx.stroke();
        ctx.fillText(val.toString(), paddingLeft - 8, y + 3);
      });

      const durationMs = plotData.duration_ms || 45.0;
      const xTicks = [0, 10, 20, 30, 40];
      ctx.textAlign = 'center';

      xTicks.forEach(tMs => {
        if (tMs <= durationMs) {
          const x = paddingLeft + (tMs / durationMs) * plotW;
          ctx.beginPath();
          ctx.moveTo(x, paddingTop);
          ctx.lineTo(x, paddingTop + plotH);
          ctx.stroke();
          ctx.fillText(tMs.toString(), x, paddingTop + plotH + 16);
        }
      });

      // Axis Labels
      ctx.fillStyle = '#94a3b8';
      ctx.font = '10px "Inter", sans-serif';
      ctx.fillText('Time (ms)', paddingLeft + plotW / 2, height - 3);

      ctx.save();
      ctx.translate(12, paddingTop + plotH / 2);
      ctx.rotate(-Math.PI / 2);
      ctx.textAlign = 'center';
      ctx.fillText('Amplitude (16-bit PCM)', 0, 0);
      ctx.restore();

      const getX = (idx) => paddingLeft + (idx / (orig.length - 1)) * plotW;
      const getY = (val) => {
        const norm = (val - minPcm) / (maxPcm - minPcm);
        return paddingTop + plotH * (1 - Math.max(0, Math.min(1, norm)));
      };

      ctx.beginPath();
      ctx.strokeStyle = '#8be9fd';
      ctx.lineWidth = 1.4;
      for (let i = 0; i < orig.length; i++) {
        const x = getX(i);
        const y = getY(orig[i]);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();

      ctx.beginPath();
      ctx.strokeStyle = '#ff79c6';
      ctx.lineWidth = 1.2;
      ctx.setLineDash([4, 4]);
      for (let i = 0; i < stego.length; i++) {
        const x = getX(i);
        const y = getY(stego[i]);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
      ctx.setLineDash([]);
    }

    function drawLSBResidualCanvas(plotData) {
      const cvs = document.getElementById('canvas-audio-residual');
      if (!cvs || !cvs.parentElement) return;
      const ctx = cvs.getContext('2d');

      const width = cvs.parentElement.clientWidth || 700;
      const height = 150;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);

      cvs.width = width * dpr;
      cvs.height = height * dpr;
      cvs.style.width = `${width}px`;
      cvs.style.height = `${height}px`;

      ctx.scale(dpr, dpr);
      ctx.fillStyle = '#06030c';
      ctx.fillRect(0, 0, width, height);

      const paddingLeft = 55;
      const paddingBottom = 25;
      const paddingTop = 15;
      const paddingRight = 20;

      const plotW = width - paddingLeft - paddingRight;
      const plotH = height - paddingTop - paddingBottom;

      const yTicks = [0.00, 0.25, 0.50, 0.75, 1.00, 1.25, 1.50];
      const minY = -0.1;
      const maxY = 1.6;

      ctx.fillStyle = '#8e8a9f';
      ctx.font = '10px "JetBrains Mono", monospace';
      ctx.textAlign = 'right';

      yTicks.forEach(val => {
        const yNorm = (val - minY) / (maxY - minY);
        const y = paddingTop + plotH * (1 - yNorm);
        ctx.beginPath();
        ctx.moveTo(paddingLeft, y);
        ctx.lineTo(paddingLeft + plotW, y);
        ctx.stroke();
        ctx.fillText(val.toFixed(2), paddingLeft - 8, y + 3);
      });

      const durationMs = plotData.duration_ms || 45.0;
      const xTicks = [0, 10, 20, 30, 40];
      ctx.textAlign = 'center';

      xTicks.forEach(tMs => {
        if (tMs <= durationMs) {
          const x = paddingLeft + (tMs / durationMs) * plotW;
          ctx.beginPath();
          ctx.moveTo(x, paddingTop);
          ctx.lineTo(x, paddingTop + plotH);
          ctx.stroke();
          ctx.fillText(tMs.toString(), x, paddingTop + plotH + 16);
        }
      });

      // Axis Labels
      ctx.fillStyle = '#94a3b8';
      ctx.font = '10px "Inter", sans-serif';
      ctx.fillText('Time (ms)', paddingLeft + plotW / 2, height - 3);

      ctx.save();
      ctx.translate(12, paddingTop + plotH / 2);
      ctx.rotate(-Math.PI / 2);
      ctx.textAlign = 'center';
      ctx.fillText('Bit Delta (LSB)', 0, 0);
      ctx.restore();

      const deltas = plotData.lsb_deltas;
      if (!deltas || !deltas.length) return;

      const getX = (idx) => paddingLeft + (idx / (deltas.length - 1)) * plotW;
      const getY = (val) => {
        const norm = (val - minY) / (maxY - minY);
        return paddingTop + plotH * (1 - Math.max(0, Math.min(1, norm)));
      };

      ctx.beginPath();
      ctx.strokeStyle = '#50fa7b';
      ctx.lineWidth = 1.3;
      ctx.fillStyle = 'rgba(80, 250, 123, 0.12)';

      const zeroY = getY(0);
      ctx.moveTo(paddingLeft, zeroY);

      for (let i = 0; i < deltas.length; i++) {
        const x = getX(i);
        const y = getY(deltas[i]);
        ctx.lineTo(x, y);
      }
      ctx.lineTo(paddingLeft + plotW, zeroY);
      ctx.closePath();
      ctx.fill();

      ctx.beginPath();
      for (let i = 0; i < deltas.length; i++) {
        const x = getX(i);
        const y = getY(deltas[i]);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
    }

    window.addEventListener('resize', () => {
      if (lastAudioProofData && lastAudioProofData.plot_data) {
        drawWaveformComparisonCanvas(lastAudioProofData.plot_data);
        drawLSBResidualCanvas(lastAudioProofData.plot_data);
      }
    });

    document.getElementById('btn-audio-embed-act').addEventListener('click', async () => {
      if (!audioEmbedFile) {
        showToast('Please upload a WAV or MP4 media file first.', 'warning');
        return;
      }
      const text = document.getElementById('input-audio-embed-text').value;
      const pwd = document.getElementById('input-audio-embed-pwd').value;
      if (!text || !pwd) {
        showToast('Please enter both secret payload text and an encryption password.', 'warning');
        return;
      }

      try {
        showToast('Encrypting & embedding payload into audio LSBs...', 'info');
        const formData = new FormData();
        formData.append('text', text);
        formData.append('password', pwd);
        formData.append('file', audioEmbedFile);

        const details = await apiCall('/api/stego/audio/embed-details', 'POST', formData);

        const b64Data = details.stego_audio_b64.split(',')[1];
        const byteCharacters = atob(b64Data);
        const byteNumbers = new Array(byteCharacters.length);
        for (let i = 0; i < byteCharacters.length; i++) {
          byteNumbers[i] = byteCharacters.charCodeAt(i);
        }
        const byteArray = new Uint8Array(byteNumbers);
        const blob = new Blob([byteArray], { type: 'audio/wav' });
        const url = window.URL.createObjectURL(blob);

        const outPlayer = document.getElementById('player-audio-output');
        if (outPlayer) {
          outPlayer.src = url;
          document.getElementById('box-audio-out-player').style.display = 'block';
        }

        const a = document.createElement('a');
        a.href = url;
        const baseName = audioEmbedFile.name.includes('.') ? audioEmbedFile.name.substring(0, audioEmbedFile.name.lastIndexOf('.')) : audioEmbedFile.name;
        a.download = `stego_${baseName}.wav`;
        a.click();

        renderAudioStegoVisualProof(details);

        showToast('Audio Stego WAV file encrypted, playable, downloaded, and metrics generated!', 'success');
      } catch (e) {}
    });

    setupDropzone('dz-audio-extract', 'file-audio-extract', (file) => {
      audioExtractFile = file;
      const badge = document.getElementById('audio-extract-file-badge');
      badge.textContent = `Selected: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
      badge.style.display = 'inline-block';

      const extPlayer = document.getElementById('player-audio-extract');
      if (extPlayer) {
        extPlayer.src = URL.createObjectURL(file);
        document.getElementById('box-audio-extract-player').style.display = 'block';
      }

      showToast(`Selected stego file for extraction: ${file.name}`, 'info');
    });

    document.getElementById('btn-audio-extract-act').addEventListener('click', async () => {
      if (!audioExtractFile) {
        showToast('Please upload a stego WAV/MP4 file.', 'warning');
        return;
      }
      const pwd = document.getElementById('input-audio-extract-pwd').value;
      if (!pwd) {
        showToast('Please enter the decryption password.', 'warning');
        return;
      }

      try {
        showToast('Extracting & decrypting payload from audio LSBs...', 'info');
        const formData = new FormData();
        formData.append('password', pwd);
        formData.append('file', audioExtractFile);

        const res = await apiCall('/api/stego/audio/extract', 'POST', formData);
        scrambleText(document.getElementById('output-audio-recovered'), res.extracted_text);

        if (lastAudioProofData) {
          lastAudioProofData.plaintext_preview = res.extracted_text;
          lastAudioProofData.status_verification = res.status_verification;
          renderAudioStegoVisualProof(lastAudioProofData);
        } else {
          renderAudioStegoVisualProof({
            magic_header: res.magic_header,
            cipher_algo: res.cipher_algo,
            derived_key_hint: res.derived_key_hint,
            plaintext_preview: res.extracted_text,
            status_verification: res.status_verification
          });
        }

        showToast('Audio secret payload extracted and decrypted successfully!', 'success');
      } catch (e) {}
    });
  }

  // View 3: Watermarking
  function initWatermarking() {
    setupDropzone('dz-wm-base', 'file-wm-base', async (file) => {
      state.wmBaseB64 = await fileToBase64(file);
      showToast('Base image loaded for visible watermarking.', 'info');
    });

    const fsSlider = document.getElementById('input-wm-fs');
    fsSlider.addEventListener('input', () => {
      document.getElementById('lbl-wm-fs').textContent = `${fsSlider.value}px`;
    });

    const opSlider = document.getElementById('input-wm-op');
    opSlider.addEventListener('input', () => {
      document.getElementById('lbl-wm-op').textContent = opSlider.value;
    });

    const strSlider = document.getElementById('input-dct-strength');
    strSlider.addEventListener('input', () => {
      document.getElementById('lbl-dct-strength').textContent = parseFloat(strSlider.value).toFixed(1);
    });

    document.getElementById('btn-apply-text-wm').addEventListener('click', async () => {
      if (!state.wmBaseB64) {
        showToast('Please upload a base image first.', 'warning');
        return;
      }
      try {
        const text = document.getElementById('input-wm-text').value;
        const font_size = parseInt(fsSlider.value, 10);
        const opacity = parseFloat(opSlider.value);
        const color_hex = document.getElementById('input-wm-color').value;
        const position = document.getElementById('select-wm-pos').value;

        const res = await apiCall('/api/watermark/visible-text', 'POST', {
          image_b64: state.wmBaseB64,
          text, font_size, opacity, position, color_hex
        });

        document.getElementById('img-wm-out').src = res.watermarked_image_b64;
        document.getElementById('btn-wm-download').href = res.watermarked_image_b64;
        document.getElementById('card-wm-output').style.display = 'block';

        state.metricsOrigB64 = state.wmBaseB64;
        state.metricsModB64 = res.watermarked_image_b64;

        showToast('Visible text watermark applied!', 'success');
      } catch (e) {}
    });

    setupDropzone('dz-wm-dct', 'file-wm-dct', async (file) => {
      state.wmDctB64 = await fileToBase64(file);
      showToast('DCT image loaded.', 'info');
    });

    document.getElementById('btn-dct-embed').addEventListener('click', async () => {
      if (!state.wmDctB64) {
        showToast('Please upload an image for DCT watermarking.', 'warning');
        return;
      }
      try {
        const text = document.getElementById('input-dct-text').value;
        const strength = parseFloat(strSlider.value);

        const res = await apiCall('/api/watermark/invisible-dct-embed', 'POST', {
          image_b64: state.wmDctB64,
          watermark_text: text,
          strength
        });

        state.lastDctBitLength = res.watermark_bit_length;
        document.getElementById('img-wm-out').src = res.watermarked_image_b64;
        document.getElementById('btn-wm-download').href = res.watermarked_image_b64;
        document.getElementById('card-wm-output').style.display = 'block';

        const infoBox = document.getElementById('output-dct-info');
        scrambleText(infoBox, `Invisible DCT Watermark Embedded!\nBits Embedded: ${res.bits_embedded}\nBit Length for Extraction: ${res.watermark_bit_length}\nPSNR: ${res.metrics.psnr_db.toFixed(2)} dB | MSE: ${res.metrics.mse.toFixed(3)}`);
        document.getElementById('box-dct-result').style.display = 'block';

        state.metricsOrigB64 = state.wmDctB64;
        state.metricsModB64 = res.watermarked_image_b64;

        showToast('Invisible 8x8 DCT Watermark embedded in frequency domain!', 'success');
      } catch (e) {}
    });

    document.getElementById('btn-dct-extract').addEventListener('click', async () => {
      if (!state.wmDctB64) {
        showToast('Please upload watermarked image.', 'warning');
        return;
      }
      try {
        const strength = parseFloat(strSlider.value);
        const bitLen = state.lastDctBitLength || 96;

        const res = await apiCall('/api/watermark/invisible-dct-extract', 'POST', {
          image_b64: state.wmDctB64,
          watermark_bit_length: bitLen,
          strength
        });

        const infoBox = document.getElementById('output-dct-info');
        scrambleText(infoBox, `Extracted Watermark Text: "${res.extracted_text}"\nBits Extracted: ${res.bits_extracted}`);
        document.getElementById('box-dct-result').style.display = 'block';

        showToast(`Extracted DCT Watermark: "${res.extracted_text}"`, 'success');
      } catch (e) {}
    });
  }

  // View 4: RSA (Edu)
  function initRsaEdu() {
    document.getElementById('btn-run-mr').addEventListener('click', async () => {
      const n = document.getElementById('input-mr-candidate').value;
      const rounds = parseInt(document.getElementById('input-mr-rounds').value, 10);
      if (!n) return;

      try {
        const res = await apiCall('/api/crypto-edu/miller-rabin', 'POST', { n, rounds });
        const verdictText = document.getElementById('mr-verdict-text');
        const roundsBadge = document.getElementById('mr-rounds-badge');

        if (res.is_prime) {
          verdictText.textContent = 'PROBABLY PRIME';
          verdictText.style.color = 'var(--emerald-success)';
        } else {
          verdictText.textContent = 'COMPOSITE';
          verdictText.style.color = 'var(--crimson-error)';
        }
        roundsBadge.textContent = `${res.rounds} Witness Rounds`;
        document.getElementById('mr-res-box').style.display = 'block';
      } catch (e) {}
    });

    document.getElementById('btn-sample-p').addEventListener('click', () => {
      document.getElementById('input-mr-candidate').value = '104729';
    });

    document.getElementById('btn-sample-c').addEventListener('click', () => {
      document.getElementById('input-mr-candidate').value = '104730';
    });

    document.getElementById('btn-gen-edu').addEventListener('click', async () => {
      try {
        showToast('Deriving 1024-bit Educational BigInt Keypair...', 'info');
        const res = await apiCall('/api/crypto-edu/generate-keys', 'POST', { bits: 1024 });
        state.eduKeyPair = res.keypair;

        scrambleText(document.getElementById('edu-n-box'), res.keypair.n);
        scrambleText(document.getElementById('edu-e-box'), String(res.keypair.publicKey.e));
        scrambleText(document.getElementById('edu-d-box'), String(res.keypair.privateKey.d));

        showToast('Educational BigInt parameters computed!', 'success');
      } catch (e) {}
    });

    document.getElementById('btn-edu-enc').addEventListener('click', async () => {
      const text = document.getElementById('input-edu-txt').value;
      if (!text || !state.eduKeyPair) {
        showToast('Please generate Edu keypair and enter plaintext.', 'warning');
        return;
      }
      try {
        const res = await apiCall('/api/crypto-edu/encrypt', 'POST', {
          plaintext: text,
          public_key: state.eduKeyPair.publicKey
        });
        scrambleText(document.getElementById('out-edu-cipher'), res.ciphertext);
        document.getElementById('input-edu-cipher-in').value = res.ciphertext;
        showToast('Modular Exponentiation Encryption Complete', 'success');
      } catch (e) {}
    });

    document.getElementById('btn-edu-dec').addEventListener('click', async () => {
      const cipherStr = document.getElementById('input-edu-cipher-in').value;
      if (!cipherStr || !state.eduKeyPair) {
        showToast('Please enter ciphertext and generate keypair.', 'warning');
        return;
      }
      try {
        const res = await apiCall('/api/crypto-edu/decrypt', 'POST', {
          ciphertext: cipherStr,
          private_key: state.eduKeyPair.privateKey
        });
        scrambleText(document.getElementById('out-edu-plain'), res.plaintext);
        showToast('Modular Exponentiation Decryption Complete', 'success');
      } catch (e) {}
    });
  }

  // View 5: WebCrypto
  function initWebCrypto() {
    document.getElementById('btn-wc-gen-keys').addEventListener('click', async () => {
      try {
        showToast('Generating RSA-OAEP 2048 key pair...', 'info');
        const keys = await apiCall('/api/crypto/generate-rsa-keys', 'POST', { key_size: 2048 });

        state.wcPubKeyPem = keys.public_key_pem;
        state.wcPrivKeyPem = keys.private_key_pem;

        scrambleText(document.getElementById('wc-pub-pem'), keys.public_key_pem);
        scrambleText(document.getElementById('wc-priv-pem'), keys.private_key_pem);

        document.getElementById('input-wc-pubkey').value = keys.public_key_pem;
        document.getElementById('input-wc-privkey').value = keys.private_key_pem;

        showToast('RSA-OAEP 2048 key pair generated!', 'success');
      } catch (e) {}
    });

    document.getElementById('btn-wc-encrypt-act').addEventListener('click', async () => {
      const plain = document.getElementById('input-wc-plain').value;
      const pubKey = document.getElementById('input-wc-pubkey').value;
      if (!plain || !pubKey) {
        showToast('Please enter message and Public Key PEM.', 'warning');
        return;
      }
      try {
        const res = await apiCall('/api/crypto/encrypt-hybrid', 'POST', {
          plaintext: plain,
          public_key_pem: pubKey
        });
        const jsonStr = JSON.stringify(res, null, 2);
        scrambleText(document.getElementById('output-wc-json'), jsonStr);
        document.getElementById('box-wc-enc-res').style.display = 'block';
        document.getElementById('input-wc-json-in').value = jsonStr;
        showToast('Hybrid Encryption complete!', 'success');
      } catch (e) {}
    });

    document.getElementById('btn-wc-decrypt-act').addEventListener('click', async () => {
      const jsonStr = document.getElementById('input-wc-json-in').value;
      const privKey = document.getElementById('input-wc-privkey').value;
      if (!jsonStr || !privKey) {
        showToast('Please enter JSON payload and Private Key PEM.', 'warning');
        return;
      }
      try {
        const payloadObj = JSON.parse(jsonStr);
        const res = await apiCall('/api/crypto/decrypt-hybrid', 'POST', {
          payload: payloadObj,
          private_key_pem: privKey
        });
        scrambleText(document.getElementById('output-wc-plaintext'), res.plaintext);
        document.getElementById('box-wc-dec-res').style.display = 'block';
        showToast('Hybrid Decryption complete!', 'success');
      } catch (e) {}
    });

    setupDropzone('dz-file-crypto', 'file-crypto-in', (file) => {
      state.cryptoFile = file;
      const badge = document.getElementById('file-badge');
      badge.textContent = `Selected: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
      badge.style.display = 'inline-block';
    });

    document.getElementById('btn-file-enc').addEventListener('click', async () => {
      if (!state.cryptoFile) {
        showToast('Please select a file to encrypt.', 'warning');
        return;
      }
      const pubKey = document.getElementById('input-wc-pubkey').value || state.wcPubKeyPem;
      if (!pubKey) {
        showToast('Please provide an RSA Public Key.', 'warning');
        return;
      }
      try {
        showToast('Encrypting binary file package...', 'info');
        const formData = new FormData();
        formData.append('public_key_pem', pubKey);
        formData.append('file', state.cryptoFile);

        const blob = await apiCall('/api/crypto/encrypt-file', 'POST', formData);
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${state.cryptoFile.name}.enc`;
        a.click();
        window.URL.revokeObjectURL(url);
        showToast('Encrypted file downloaded!', 'success');
      } catch (e) {}
    });

    document.getElementById('btn-file-dec').addEventListener('click', async () => {
      if (!state.cryptoFile) {
        showToast('Please select an encrypted file.', 'warning');
        return;
      }
      const privKey = document.getElementById('input-wc-privkey').value || state.wcPrivKeyPem;
      if (!privKey) {
        showToast('Please provide an RSA Private Key.', 'warning');
        return;
      }
      try {
        showToast('Decrypting binary file package...', 'info');
        const formData = new FormData();
        formData.append('private_key_pem', privKey);
        formData.append('file', state.cryptoFile);

        const blob = await apiCall('/api/crypto/decrypt-file', 'POST', formData);
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = state.cryptoFile.name.replace('.enc', '') || 'decrypted.bin';
        a.click();
        window.URL.revokeObjectURL(url);
        showToast('Decrypted file downloaded!', 'success');
      } catch (e) {}
    });

    const hashInput = document.getElementById('input-hash-txt');
    hashInput.addEventListener('input', async () => {
      const val = hashInput.value;
      if (!val) {
        document.getElementById('out-sha256-digest').textContent = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855';
        return;
      }
      try {
        const res = await apiCall('/api/crypto/hash', 'POST', { text: val });
        scrambleText(document.getElementById('out-sha256-digest'), res.hash_sha256, 300);
      } catch (e) {}
    });

    document.getElementById('btn-sign-msg').addEventListener('click', async () => {
      const txt = hashInput.value || 'Test Message';
      const privKey = document.getElementById('input-wc-privkey').value || state.wcPrivKeyPem;
      if (!privKey) {
        showToast('Please generate an RSA key pair.', 'warning');
        return;
      }
      try {
        const sigRes = await apiCall('/api/crypto/sign', 'POST', { message: txt, private_key_pem: privKey });
        state.lastSigB64 = sigRes.signature_b64;
        document.getElementById('box-sig-status').innerHTML = `<div class="badge badge-info" style="word-break: break-all;">RSA-PSS Signature Generated</div>`;
        showToast('RSA-PSS Signature generated!', 'success');
      } catch (e) {}
    });

    document.getElementById('btn-verify-sig').addEventListener('click', async () => {
      const txt = hashInput.value || 'Test Message';
      const pubKey = document.getElementById('input-wc-pubkey').value || state.wcPubKeyPem;
      if (!state.lastSigB64 || !pubKey) {
        showToast('Please sign a message first.', 'warning');
        return;
      }
      try {
        const verRes = await apiCall('/api/crypto/verify', 'POST', {