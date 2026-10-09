/**
 * TaikoNation Web UI Client Logic
 * Handles file drop, settings, API generation requests,
 * and animated Taiko lane preview with Web Audio.
 */

document.addEventListener('DOMContentLoaded', () => {
  // Elements
  const tabUpload = document.getElementById('tab-upload');
  const tabPresets = document.getElementById('tab-presets');
  const modeUpload = document.getElementById('mode-upload');
  const modePresets = document.getElementById('mode-presets');

  const dropZone = document.getElementById('drop-zone');
  const audioInput = document.getElementById('audio-input');
  const fileInfo = document.getElementById('file-info');
  const fileNameSpan = document.getElementById('file-name');
  const fileSizeSpan = document.getElementById('file-size');

  const presetSelect = document.getElementById('preset-select');
  const inputTitle = document.getElementById('input-title');
  const inputArtist = document.getElementById('input-artist');
  const inputDiff = document.getElementById('input-diff');

  const sliderDensity = document.getElementById('slider-density');
  const valDensity = document.getElementById('val-density');
  const sliderTemp = document.getElementById('slider-temp');
  const valTemp = document.getElementById('val-temp');

  const btnGenerate = document.getElementById('btn-generate');

  const placeholderView = document.getElementById('placeholder-view');
  const processingView = document.getElementById('processing-view');
  const completedView = document.getElementById('completed-view');
  const processingText = document.getElementById('processing-text');
  const progressFill = document.getElementById('progress-fill');
  const resultStatusBadge = document.getElementById('result-status-badge');

  const resTitle = document.getElementById('res-title');
  const resArtist = document.getElementById('res-artist');
  const resTotalNotes = document.getElementById('res-total-notes');
  const resDonCount = document.getElementById('res-don-count');
  const resKatCount = document.getElementById('res-kat-count');
  const resDuration = document.getElementById('res-duration');

  const btnDownloadOsz = document.getElementById('btn-download-osz');
  const btnDownloadOsu = document.getElementById('btn-download-osu');

  const canvas = document.getElementById('taiko-canvas');
  const ctx = canvas.getContext('2d');
  const btnPlayPause = document.getElementById('btn-play-pause');
  const iconPlay = document.getElementById('icon-play');
  const iconPause = document.getElementById('icon-pause');
  const timeDisplay = document.getElementById('time-display');
  const audioPlayer = document.getElementById('audio-player');

  // State
  let currentMode = 'upload'; // 'upload' | 'preset'
  let selectedFile = null;
  let currentTaskId = null;
  let previewNotes = [];
  let isPlaying = false;
  let animationFrameId = null;
  let playbackStartTime = 0;
  let simulatedDuration = 0;

  // Sliders
  sliderDensity.addEventListener('input', (e) => {
    valDensity.textContent = `${parseFloat(e.target.value).toFixed(1)}x`;
  });
  sliderTemp.addEventListener('input', (e) => {
    valTemp.textContent = parseFloat(e.target.value).toFixed(2);
  });

  // Tab Switch
  tabUpload.addEventListener('click', () => {
    currentMode = 'upload';
    tabUpload.classList.add('active');
    tabPresets.classList.remove('active');
    modeUpload.classList.remove('hidden');
    modePresets.classList.add('hidden');
    checkCanGenerate();
  });

  tabPresets.addEventListener('click', () => {
    currentMode = 'preset';
    tabPresets.classList.add('active');
    tabUpload.classList.remove('active');
    modePresets.classList.remove('hidden');
    modeUpload.classList.add('hidden');
    loadPresets();
    checkCanGenerate();
  });

  // Load Presets
  async function loadPresets() {
    try {
      const res = await fetch('/api/presets');
      const data = await res.json();
      presetSelect.innerHTML = '<option value="" disabled selected>楽曲を選択してください</option>';
      data.presets.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p.id;
        opt.textContent = p.name;
        presetSelect.appendChild(opt);
      });
    } catch (e) {
      presetSelect.innerHTML = '<option value="" disabled selected>プリセット読込エラー</option>';
    }
  }

  presetSelect.addEventListener('change', () => {
    const selectedOption = presetSelect.options[presetSelect.selectedIndex];
    if (selectedOption) {
      const parts = selectedOption.textContent.split(' - ');
      if (parts.length >= 2) {
        inputArtist.value = parts[0];
        inputTitle.value = parts.slice(1).join(' - ');
      } else {
        inputArtist.value = 'TaikoNation';
        inputTitle.value = selectedOption.textContent;
      }
    }
    checkCanGenerate();
  });

  // File Drop
  dropZone.addEventListener('click', () => audioInput.click());

  dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('dragover');
  });

  dropZone.addEventListener('dragleave', () => {
    dropZone.classList.remove('dragover');
  });

  dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  });

  audioInput.addEventListener('change', (e) => {
    if (e.target.files && e.target.files[0]) {
      handleFileSelected(e.target.files[0]);
    }
  });

  function handleFileSelected(file) {
    selectedFile = file;
    fileNameSpan.textContent = file.name;
    const mb = (file.size / (1024 * 1024)).toFixed(2);
    fileSizeSpan.textContent = `(${mb} MB)`;
    fileInfo.classList.remove('hidden');

    // Auto-fill title from filename
    const stem = file.name.substring(0, file.name.lastIndexOf('.')) || file.name;
    if (stem.includes(' - ')) {
      const parts = stem.split(' - ');
      inputArtist.value = parts[0].trim();
      inputTitle.value = parts.slice(1).join(' - ').trim();
    } else {
      inputTitle.value = stem.trim();
    }

    checkCanGenerate();
  }

  function checkCanGenerate() {
    if (currentMode === 'upload') {
      btnGenerate.disabled = !selectedFile;
    } else {
      btnGenerate.disabled = !presetSelect.value;
    }
  }

  // Generation Action
  btnGenerate.addEventListener('click', async () => {
    btnGenerate.disabled = true;
    placeholderView.classList.add('hidden');
    completedView.classList.add('hidden');
    processingView.classList.remove('hidden');
    resultStatusBadge.textContent = '生成中 (Generating)';
    resultStatusBadge.style.color = '#ffbe2e';
    progressFill.style.width = '20%';

    try {
      let res;
      if (currentMode === 'upload') {
        const formData = new FormData();
        formData.append('file', selectedFile);
        formData.append('title', inputTitle.value);
        formData.append('artist', inputArtist.value);
        formData.append('difficulty', inputDiff.value);
        formData.append('temperature', sliderTemp.value);
        formData.append('density', sliderDensity.value);

        progressFill.style.width = '40%';
        processingText.textContent = '音楽特徴量抽出中 (Analyzing spectrogram)...';

        res = await fetch('/api/generate', {
          method: 'POST',
          body: formData
        });
      } else {
        const formData = new FormData();
        formData.append('preset_name', presetSelect.value);
        formData.append('difficulty', inputDiff.value);
        formData.append('temperature', sliderTemp.value);
        formData.append('density', sliderDensity.value);

        progressFill.style.width = '60%';
        processingText.textContent = 'ニューラルネットワーク推論中...';

        res = await fetch('/api/generate-preset', {
          method: 'POST',
          body: formData
        });
      }

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Generation failed');
      }

      progressFill.style.width = '100%';
      processingText.textContent = '完了！ (Finished)';

      const result = await res.json();
      currentTaskId = result.task_id;
      showCompletedResult(result);

    } catch (err) {
      alert(`生成エラー: ${err.message}`);
      processingView.classList.add('hidden');
      placeholderView.classList.remove('hidden');
      resultStatusBadge.textContent = 'エラー (Error)';
      resultStatusBadge.style.color = '#ff3e4e';
    } finally {
      btnGenerate.disabled = false;
    }
  });

  function showCompletedResult(data) {
    processingView.classList.add('hidden');
    completedView.classList.remove('hidden');
    resultStatusBadge.textContent = '生成完了 (Success)';
    resultStatusBadge.style.color = '#4ade80';

    resTitle.textContent = data.title;
    resArtist.textContent = data.artist;
    resTotalNotes.textContent = data.total_notes;
    resDonCount.textContent = data.don_count + (data.big_don_count || 0);
    resKatCount.textContent = data.kat_count + (data.big_kat_count || 0);

    const mins = Math.floor(data.duration / 60);
    const secs = Math.floor(data.duration % 60).toString().padStart(2, '0');
    resDuration.textContent = `${mins}:${secs}`;
    simulatedDuration = data.duration;

    // Downloads
    if (data.has_audio === false) {
      btnDownloadOsz.disabled = true;
      btnDownloadOsz.style.opacity = '0.4';
      btnDownloadOsz.title = 'プリセット生成時は音声ファイルがないため.osuのみ利用可能です';
    } else {
      btnDownloadOsz.disabled = false;
      btnDownloadOsz.style.opacity = '1';
    }

    btnDownloadOsz.onclick = () => {
      window.location.href = `/api/download/${currentTaskId}/osz`;
    };
    btnDownloadOsu.onclick = () => {
      window.location.href = `/api/download/${currentTaskId}/osu`;
    };

    // Audio Player setup
    if (data.audio_url) {
      audioPlayer.src = data.audio_url;
      audioPlayer.load();
    } else {
      audioPlayer.removeAttribute('src');
    }

    // Lane preview setup
    previewNotes = data.notes_preview || [];
    stopPlayback();
    drawLane(0);
  }

  // Playback & Canvas Animation
  btnPlayPause.addEventListener('click', () => {
    if (isPlaying) {
      pausePlayback();
    } else {
      startPlayback();
    }
  });

  function startPlayback() {
    isPlaying = true;
    iconPlay.classList.add('hidden');
    iconPause.classList.remove('hidden');

    if (audioPlayer.src) {
      audioPlayer.play();
    } else {
      playbackStartTime = performance.now();
    }

    animateLane();
  }

  function pausePlayback() {
    isPlaying = false;
    iconPlay.classList.remove('hidden');
    iconPause.classList.add('hidden');
    if (audioPlayer.src) {
      audioPlayer.pause();
    }
    if (animationFrameId) {
      cancelAnimationFrame(animationFrameId);
    }
  }

  function stopPlayback() {
    pausePlayback();
    if (audioPlayer.src) {
      audioPlayer.currentTime = 0;
    }
    drawLane(0);
    updateTimeDisplay(0, simulatedDuration);
  }

  audioPlayer.addEventListener('ended', () => {
    stopPlayback();
  });

  function animateLane() {
    if (!isPlaying) return;

    let currentSec = 0;
    if (audioPlayer.src && !isNaN(audioPlayer.currentTime)) {
      currentSec = audioPlayer.currentTime;
    } else {
      currentSec = (performance.now() - playbackStartTime) / 1000;
      if (currentSec > simulatedDuration) {
        stopPlayback();
        return;
      }
    }

    drawLane(currentSec);
    updateTimeDisplay(currentSec, simulatedDuration);
    animationFrameId = requestAnimationFrame(animateLane);
  }

  function updateTimeDisplay(current, total) {
    const cM = Math.floor(current / 60);
    const cS = Math.floor(current % 60).toString().padStart(2, '0');
    const tM = Math.floor(total / 60);
    const tS = Math.floor(total % 60).toString().padStart(2, '0');
    timeDisplay.textContent = `${cM}:${cS} / ${tM}:${tS}`;
  }

  // Draw Taiko Lane
  function drawLane(currentTimeSec) {
    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);

    // Lane background
    ctx.fillStyle = '#151926';
    ctx.fillRect(0, 0, w, h);

    // Center rail
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(0, h / 2);
    ctx.lineTo(w, h / 2);
    ctx.stroke();

    // Hit Target Circle
    const targetX = 90;
    const centerY = h / 2;

    // Drum target
    ctx.fillStyle = '#22283a';
    ctx.beginPath();
    ctx.arc(targetX, centerY, 34, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = 3;
    ctx.stroke();

    // Draw notes
    // 1 chunk = 23ms = 0.023s
    // Speed: 400px per second
    const speed = 400;

    for (let i = 0; i < previewNotes.length; i++) {
      const noteType = previewNotes[i];
      if (noteType === 0) continue; // silence

      const noteTime = i * 0.023; // seconds
      const delta = noteTime - currentTimeSec;
      const x = targetX + delta * speed;

      // Only draw visible notes
      if (x < -40 || x > w + 40) continue;

      let radius = 22;
      let color = '#ff3e4e'; // Don (small)

      if (noteType === 1) { // Don
        radius = 20;
        color = '#ff3e4e';
      } else if (noteType === 2) { // Kat
        radius = 20;
        color = '#229fff';
      } else if (noteType === 3) { // Big Don
        radius = 28;
        color = '#ff3e4e';
      } else if (noteType === 4) { // Big Kat
        radius = 28;
        color = '#229fff';
      } else if (noteType >= 5) { // Drumroll
        radius = 18;
        color = '#ffbe2e';
      }

      // Outer glow / border
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(x, centerY, radius, 0, Math.PI * 2);
      ctx.fill();

      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 3.5;
      ctx.stroke();

      // Inner icon or mark
      ctx.fillStyle = '#ffffff';
      ctx.beginPath();
      ctx.arc(x, centerY, radius * 0.35, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  // Initial Lane Render
  drawLane(0);
});
