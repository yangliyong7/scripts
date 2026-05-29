/* global speechSynthesis */
(function () {
  "use strict";

  const $ = (sel, el = document) => el.querySelector(sel);
  const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];

  const US_VOICE_PATTERNS = [
    /Jenny/i,
    /Aria/i,
    /Guy/i,
    /Microsoft (Zira|David)/i,
    /Google US English/i,
    /Samantha/i,
    /Karen/i,
    /Daniel/i,
    /en-US/i,
  ];

  let manifest = [];
  let currentStory = null;
  let currentWords = [];
  let unitNum = "1";
  let audioManifest = null;
  let audioBase = "";
  let htmlAudio = null;
  let fontScale = 0;
  let selectedVoiceURI = localStorage.getItem("vocab_tts_voice") || "";
  let trackMeta = null;
  let trackMetaPromise = null;
  let playback = {
    mode: null,
    partIndex: 0,
    wasPlaying: false,
    aborted: false,
    userSeeking: false,
  };

  const synth = window.speechSynthesis;
  const canSpeak = !!synth;

  function unitPadded(n) {
    return String(n).padStart(3, "0");
  }

  function hasNeuralAudio() {
    return !!(audioManifest && audioManifest.parts && audioManifest.parts.length);
  }

  function getEnVoices() {
    return synth.getVoices().filter((v) => /^en(-|$)/i.test(v.lang));
  }

  function pickVoice() {
    const voices = getEnVoices();
    if (selectedVoiceURI) {
      const chosen = voices.find((v) => v.voiceURI === selectedVoiceURI);
      if (chosen) return chosen;
    }
    for (const re of US_VOICE_PATTERNS) {
      const v = voices.find(
        (x) => re.test(x.name) && (x.lang === "en-US" || /US/i.test(x.name))
      );
      if (v) return v;
    }
    return voices.find((v) => v.lang === "en-US") || voices[0];
  }

  function stripHtml(html) {
    const d = document.createElement("div");
    d.innerHTML = html;
    return d.textContent || "";
  }

  function formatTime(sec) {
    if (!isFinite(sec) || sec < 0) sec = 0;
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return m + ":" + String(s).padStart(2, "0");
  }

  function audioUrl(partId) {
    return `${audioBase}part-${partId}.mp3`;
  }

  function showPlayerPanel() {
    const panel = $("#playerPanel");
    if (!panel) return;
    panel.classList.remove("hidden");
    document.body.classList.add("has-player");
  }

  function hidePlayerPanel() {
    $("#playerPanel")?.classList.add("hidden");
    document.body.classList.remove("has-player");
  }

  async function ensureTrackMeta() {
    if (trackMeta) return trackMeta;
    if (trackMetaPromise) return trackMetaPromise;
    if (!hasNeuralAudio()) return null;

    trackMetaPromise = (async () => {
      const tracks = [];
      let start = 0;
      for (const p of audioManifest.parts) {
        const url = audioUrl(p.id);
        const duration = await new Promise((resolve, reject) => {
          const a = new Audio(url);
          a.preload = "metadata";
          a.addEventListener("loadedmetadata", () => resolve(a.duration || 0));
          a.addEventListener("error", () => reject(new Error(url)));
        });
        tracks.push({ id: p.id, url, duration, start });
        start += duration;
      }
      trackMeta = { tracks, totalDuration: start };
      buildPartJumps();
      return trackMeta;
    })();

    try {
      return await trackMetaPromise;
    } catch (e) {
      trackMetaPromise = null;
      throw e;
    }
  }

  function buildPartJumps() {
    const box = $("#partJumps");
    if (!box || !trackMeta) return;
    box.innerHTML = trackMeta.tracks
      .map(
        (t, i) =>
          `<button type="button" class="jump-part" data-index="${i}" data-part="${t.id}">${t.id}</button>`
      )
      .join("");
    $$(".jump-part", box).forEach((btn) => {
      btn.addEventListener("click", () => {
        const idx = parseInt(btn.dataset.index, 10);
        seekToPart(idx, 0, true);
      });
    });
  }

  function getGlobalTime(partIndex, localTime) {
    if (!trackMeta) return 0;
    const t = trackMeta.tracks[partIndex];
    return (t ? t.start : 0) + (localTime || 0);
  }

  function findAtGlobalTime(globalTime) {
    if (!trackMeta) return { index: 0, offset: 0 };
    const tracks = trackMeta.tracks;
    for (let i = tracks.length - 1; i >= 0; i--) {
      if (globalTime >= tracks[i].start - 0.01) {
        return {
          index: i,
          offset: Math.min(
            Math.max(0, globalTime - tracks[i].start),
            tracks[i].duration
          ),
        };
      }
    }
    return { index: 0, offset: 0 };
  }

  function setSeekSliderRatio(ratio) {
    const seek = $("#progressSeek");
    if (seek) seek.value = String(Math.round(Math.max(0, Math.min(1, ratio)) * 1000));
  }

  function updateProgressUI(globalTime, playingPartIndex) {
    if (!trackMeta) return;
    const total = trackMeta.totalDuration || 1;
    const ratio = Math.min(1, globalTime / total);
    if (!playback.userSeeking) setSeekSliderRatio(ratio);

    const { index } = findAtGlobalTime(globalTime);
    const partId = trackMeta.tracks[index]?.id || "?";
    const label = $("#progressLabel");
    if (label) {
      label.textContent =
        "Part " +
        partId +
        " · " +
        formatTime(globalTime) +
        " / " +
        formatTime(total);
    }

    const activeIdx =
      playingPartIndex !== undefined ? playingPartIndex : index;
    $$(".jump-part").forEach((btn) => {
      const i = parseInt(btn.dataset.index, 10);
      btn.classList.toggle("active", i === activeIdx);
      btn.classList.toggle("done", i < activeIdx);
    });

    highlightPart(trackMeta.tracks[activeIdx]?.id);
  }

  function highlightPart(partId) {
    if (!partId) return;
    $$(".story-part").forEach((el) => {
      el.classList.toggle("reading", el.dataset.part === partId);
    });
  }

  function scrollToPart(partId) {
    const el = $(`.story-part[data-part="${partId}"]`);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function clearReadingHighlight() {
    $$(".story-part.reading").forEach((el) => el.classList.remove("reading"));
  }

  function setPlayingButtons(playing) {
    if (playing) {
      $("#btnPlay")?.classList.add("hidden");
      $("#btnStop")?.classList.remove("hidden");
    } else {
      $("#btnPlay")?.classList.remove("hidden");
      $("#btnStop")?.classList.add("hidden");
    }
  }

  function onAudioTimeUpdate() {
    if (!htmlAudio || playback.mode !== "all" || !trackMeta) return;
    if (playback.userSeeking) return;
    const global = getGlobalTime(playback.partIndex, htmlAudio.currentTime);
    updateProgressUI(global, playback.partIndex);
  }

  function detachAudio() {
    if (!htmlAudio) return;
    htmlAudio.removeEventListener("timeupdate", onAudioTimeUpdate);
    htmlAudio.pause();
    htmlAudio = null;
  }

  function stopSpeech() {
    playback.aborted = true;
    playback.mode = null;
    playback.wasPlaying = false;
    if (synth.speaking) synth.cancel();
    detachAudio();
    setPlayingButtons(false);
    $$(".btn-play-part.playing").forEach((b) => b.classList.remove("playing"));
    clearReadingHighlight();
  }

  function stopAndHidePlayer() {
    stopSpeech();
    hidePlayerPanel();
  }

  function speakTextBrowser(text, onEnd) {
    if (!canSpeak || !text.trim()) return false;
    stopSpeech();
    playback.mode = "tts";
    const u = new SpeechSynthesisUtterance(text);
    const voice = pickVoice();
    if (voice) {
      u.voice = voice;
      u.lang = voice.lang || "en-US";
    } else {
      u.lang = "en-US";
    }
    u.rate = 0.9;
    playback.aborted = false;
    u.onend = () => {
      if (!playback.aborted) setPlayingButtons(false);
      if (onEnd) onEnd();
    };
    u.onerror = () => stopSpeech();
    setPlayingButtons(true);
    synth.speak(u);
    return true;
  }

  function playCurrentAudio(offset) {
    return new Promise((resolve, reject) => {
      if (!htmlAudio || playback.aborted) {
        reject(new Error("aborted"));
        return;
      }
      if (offset > 0) htmlAudio.currentTime = offset;
      htmlAudio.addEventListener("timeupdate", onAudioTimeUpdate);
      const onEnd = () => {
        htmlAudio?.removeEventListener("ended", onEnd);
        htmlAudio?.removeEventListener("error", onErr);
        resolve();
      };
      const onErr = () => {
        htmlAudio?.removeEventListener("ended", onEnd);
        htmlAudio?.removeEventListener("error", onErr);
        reject(new Error("play error"));
      };
      htmlAudio.addEventListener("ended", onEnd);
      htmlAudio.addEventListener("error", onErr);
      htmlAudio.play().catch(reject);
    });
  }

  async function playPartAtIndex(index, offsetSec) {
    if (!trackMeta || playback.aborted) return;
    const track = trackMeta.tracks[index];
    if (!track) return;

    detachAudio();
    playback.partIndex = index;
    htmlAudio = new Audio(track.url);

    $$(".btn-play-part.playing").forEach((b) => b.classList.remove("playing"));
    $(`.btn-play-part[data-part="${track.id}"]`)?.classList.add("playing");

    scrollToPart(track.id);
    updateProgressUI(getGlobalTime(index, offsetSec), index);

    await playCurrentAudio(offsetSec || 0);
    detachAudio();
    $(`.btn-play-part[data-part="${track.id}"]`)?.classList.remove("playing");
  }

  async function playAllParts(startIndex, offsetInPart) {
    if (!hasNeuralAudio()) return;
    try {
      await ensureTrackMeta();
    } catch {
      alert("无法加载音频时长，请检查网络后重试。");
      return;
    }

    stopSpeech();
    playback.mode = "all";
    playback.aborted = false;
    playback.wasPlaying = true;
    showPlayerPanel();
    setPlayingButtons(true);

    let i = startIndex || 0;
    const offset = offsetInPart || 0;

    while (i < trackMeta.tracks.length && !playback.aborted) {
      try {
        await playPartAtIndex(i, i === startIndex ? offset : 0);
      } catch {
        break;
      }
      i++;
    }

    if (!playback.aborted) {
      updateProgressUI(trackMeta.totalDuration, trackMeta.tracks.length - 1);
      setSeekSliderRatio(1);
    }
    playback.mode = null;
    playback.wasPlaying = false;
    setPlayingButtons(false);
    clearReadingHighlight();
    $$(".btn-play-part.playing").forEach((b) => b.classList.remove("playing"));
  }

  function seekToPart(index, offsetSec, autoPlay) {
    if (!trackMeta) return;
    index = Math.max(0, Math.min(index, trackMeta.tracks.length - 1));
    const global = getGlobalTime(index, offsetSec);
    updateProgressUI(global, index);
    setSeekSliderRatio(global / trackMeta.totalDuration);
    scrollToPart(trackMeta.tracks[index].id);

    if (autoPlay) {
      stopSpeech();
      playback.mode = "all";
      playback.aborted = false;
      playback.wasPlaying = true;
      showPlayerPanel();
      setPlayingButtons(true);
      (async () => {
        let i = index;
        const off = offsetSec || 0;
        while (i < trackMeta.tracks.length && !playback.aborted) {
          try {
            await playPartAtIndex(i, i === index ? off : 0);
          } catch {
            break;
          }
          i++;
        }
        if (!playback.aborted && trackMeta) {
          updateProgressUI(trackMeta.totalDuration, trackMeta.tracks.length - 1);
          setSeekSliderRatio(1);
        }
        playback.mode = null;
        playback.wasPlaying = false;
        setPlayingButtons(false);
        clearReadingHighlight();
      })();
    }
  }

  function seekToRatio(ratio, autoPlay) {
    if (!trackMeta) return;
    const global = ratio * trackMeta.totalDuration;
    const { index, offset } = findAtGlobalTime(global);
    seekToPart(index, offset, autoPlay);
  }

  async function playPart(partId) {
    if (hasNeuralAudio()) {
      try {
        await ensureTrackMeta();
        const idx = trackMeta.tracks.findIndex((t) => t.id === partId);
        if (idx >= 0) {
          stopSpeech();
          playback.mode = "part";
          playback.aborted = false;
          showPlayerPanel();
          setPlayingButtons(true);
          updateProgressUI(getGlobalTime(idx, 0), idx);
          setSeekSliderRatio(trackMeta.tracks[idx].start / trackMeta.totalDuration);
          try {
            await playPartAtIndex(idx, 0);
          } catch (e) {
            console.warn(e);
          }
          playback.mode = null;
          setPlayingButtons(false);
          return;
        }
      } catch (e) {
        console.warn("Neural audio failed", e);
      }
    }
    const partEl = $(`.story-part[data-part="${partId}"]`);
    const text = stripHtml(partEl?.querySelector(".story")?.innerHTML || "");
    speakTextBrowser(text);
  }

  function getVisiblePartId() {
    for (const part of $$(".story-part")) {
      const rect = part.getBoundingClientRect();
      if (rect.top < window.innerHeight * 0.45 && rect.bottom > 80) {
        return part.dataset.part;
      }
    }
    return $(".story-part")?.dataset.part || "A";
  }

  function renderMarkdownWords(html) {
    return html.replace(/\*\*([^*]+)\*\*/g, '<mark class="word" data-word="$1">$1</mark>');
  }

  async function loadJson(path) {
    const res = await fetch(path);
    if (!res.ok) throw new Error(path + " " + res.status);
    return res.json();
  }

  function renderIndex() {
    const list = $("#unitList");
    if (!list) return;
    list.innerHTML = manifest
      .map(
        (u) => `
      <li>
        <a href="unit.html?u=${u.unit}">
          <strong>Unit ${unitPadded(u.unit)}</strong>
          <span class="muted">${u.label} · ${u.count} 词</span>
          ${u.ready ? '<span class="badge">可学习</span>' : '<span class="badge">词表</span>'}
        </a>
      </li>`
      )
      .join("");
  }

  function showWordDetail(word) {
    const item = currentWords.find(
      (w) => w.word.toLowerCase() === word.toLowerCase()
    );
    if (!item) return;
    $("#drawerWord").textContent = item.word;
    $("#drawerGloss").textContent = item.gloss_zh || "—";
    $("#drawerId").textContent = "#" + item.id;
    openDrawer();
    $$(".word.active").forEach((m) => m.classList.remove("active"));
    const mark = $(`.word[data-word="${CSS.escape(word)}"]`);
    if (mark) mark.classList.add("active");
  }

  function openDrawer() {
    $("#drawer")?.classList.add("open");
  }

  function closeDrawer() {
    $("#drawer")?.classList.remove("open");
  }

  function renderWordList() {
    const box = $("#wordListBody");
    if (!box) return;
    box.innerHTML = currentWords
      .map(
        (w) => `
      <div class="word-item" data-jump="${w.word}">
        <strong>${w.word}</strong> <span class="muted">#${w.id}</span>
        <div class="muted">${(w.sense_in_unit || w.gloss_zh || "").split("\n")[0]}</div>
      </div>`
      )
      .join("");
    $$(".word-item", box).forEach((el) => {
      el.addEventListener("click", () => {
        const w = el.dataset.jump;
        const mark = document.querySelector(
          `.word[data-word="${CSS.escape(w)}"]`
        );
        if (mark) {
          mark.scrollIntoView({ behavior: "smooth", block: "center" });
          showWordDetail(w);
        }
      });
    });
  }

  function updateAudioModeBadge() {
    const badge = $("#audioModeBadge");
    if (!badge) return;
    if (hasNeuralAudio()) {
      const v = audioManifest.voice || "en-US-JennyNeural";
      badge.textContent = "美音 · " + v.replace("en-US-", "");
      badge.classList.add("neural");
    } else {
      badge.textContent = "浏览器 TTS";
      badge.classList.remove("neural");
    }
  }

  function populateVoiceSelect() {
    const sel = $("#voiceSelect");
    if (!sel) return;
    const voices = getEnVoices().filter(
      (v) => v.lang === "en-US" || /US|American/i.test(v.name)
    );
    const list = voices.length ? voices : getEnVoices();
    sel.innerHTML =
      '<option value="">自动（优选美式）</option>' +
      list
        .map(
          (v) =>
            `<option value="${v.voiceURI}">${v.name} (${v.lang})</option>`
        )
        .join("");
    if (selectedVoiceURI) sel.value = selectedVoiceURI;
    const bar = $(".voice-bar");
    const useBrowserVoice = !hasNeuralAudio();
    bar?.classList.toggle("hidden", !useBrowserVoice);
    document.body.classList.toggle("has-voice-bar", useBrowserVoice);
  }

  function renderUnit() {
    const meta = manifest.find((m) => String(m.unit) === String(unitNum));
    const title = meta ? meta.label : "Unit " + unitNum;
    $("#pageTitle").textContent = "Unit " + unitPadded(unitNum);
    $("#unitLabel").textContent = title;
    updateAudioModeBadge();
    populateVoiceSelect();

    trackMeta = null;
    trackMetaPromise = null;

    if (!currentStory) {
      $("#storyBody").innerHTML =
        '<p class="status">本篇故事正文尚未发布，可先使用下方词表与听读功能预习词汇。</p>';
      return;
    }

    $("#summaryZh").textContent = currentStory.summary_zh || "";
    const neural = hasNeuralAudio();
    const partsHtml = (currentStory.parts || [])
      .map((part) => {
        const paras = (part.paragraphs || [])
          .map((p) => `<p>${renderMarkdownWords(p)}</p>`)
          .join("");
        const quiz = (part.questions || [])
          .map((q, i) => `<li><strong>Q${i + 1}.</strong> ${q}</li>`)
          .join("");
        const intensive = (part.intensive || [])
          .map(
            (x) =>
              `<li><div class="en">${renderMarkdownWords(x.en)}</div><div class="muted">${x.zh}</div></li>`
          )
          .join("");
        const playBtn = neural
          ? `<button type="button" class="btn btn-play-part" data-part="${part.id}" aria-label="朗读 Part ${part.id}">▶ 本段美音</button>`
          : "";
        const img = part.image
          ? `
          <figure class="part-figure">
            <img src="${part.image}" alt="${part.title || "Part " + part.id}" loading="lazy" decoding="async" />
            ${part.image_caption_zh ? `<figcaption>${part.image_caption_zh}</figcaption>` : ""}
          </figure>`
          : "";
        return `
        <section class="card story-part" data-part="${part.id}">
          <div class="part-head">
            <h3>Part ${part.id} · ${part.title || ""}</h3>
            ${playBtn}
          </div>
          ${img}
          <div class="story">${paras}</div>
          ${quiz ? `<ol class="quiz">${quiz}</ol>` : ""}
          ${intensive ? `<ul class="intensive">${intensive}</ul>` : ""}
        </section>`;
      })
      .join("");
    $("#storyBody").innerHTML = partsHtml;

    $$(".word").forEach((mark) => {
      mark.addEventListener("click", () => showWordDetail(mark.dataset.word));
    });

    $$(".btn-play-part").forEach((btn) => {
      btn.addEventListener("click", () => playPart(btn.dataset.part));
    });

    if (neural) {
      ensureTrackMeta()
        .then(() => updateProgressUI(0, 0))
        .catch(() => {});
    }
  }

  function bindUnitPage() {
    $("#btnBack")?.addEventListener("click", () => {
      location.href = "index.html";
    });
    $("#btnWords")?.addEventListener("click", openDrawer);
    $("#btnCloseDrawer")?.addEventListener("click", closeDrawer);
    $(".drawer-backdrop")?.addEventListener("click", closeDrawer);

    $("#btnPlay")?.addEventListener("click", () => {
      playPart(getVisiblePartId());
    });

    $("#btnStop")?.addEventListener("click", stopAndHidePlayer);

    $("#btnPlayAll")?.addEventListener("click", async () => {
      if (hasNeuralAudio()) {
        if (playback.mode === "all" && playback.wasPlaying) {
          stopAndHidePlayer();
          return;
        }
        const seek = $("#progressSeek");
        const ratio = seek ? parseInt(seek.value, 10) / 1000 : 0;
        if (ratio > 0 && ratio < 1 && trackMeta) {
          const { index, offset } = findAtGlobalTime(ratio * trackMeta.totalDuration);
          await playAllParts(index, offset);
        } else {
          await playAllParts(0, 0);
        }
        return;
      }
      showPlayerPanel();
      $("#progressLabel").textContent = "浏览器朗读（无精细进度）";
      const all = $$(".story-part")
        .map((el) => stripHtml(el.querySelector(".story")?.innerHTML || ""))
        .filter(Boolean)
        .join("\n\n");
      speakTextBrowser(all);
    });

    $("#btnRestart")?.addEventListener("click", () => {
      stopSpeech();
      setSeekSliderRatio(0);
      updateProgressUI(0, 0);
      scrollToPart(trackMeta?.tracks[0]?.id || "A");
      playAllParts(0, 0);
    });

    const seek = $("#progressSeek");
    if (seek) {
      seek.addEventListener("input", () => {
        playback.userSeeking = true;
        if (!trackMeta) return;
        const ratio = parseInt(seek.value, 10) / 1000;
        const global = ratio * trackMeta.totalDuration;
        const { index } = findAtGlobalTime(global);
        const label = $("#progressLabel");
        if (label) {
          label.textContent =
            "拖动中 · Part " +
            (trackMeta.tracks[index]?.id || "?") +
            " · " +
            formatTime(global) +
            " / " +
            formatTime(trackMeta.totalDuration);
        }
        setSeekSliderRatio(ratio);
      });

      seek.addEventListener("change", () => {
        playback.userSeeking = false;
        if (!trackMeta) return;
        const ratio = parseInt(seek.value, 10) / 1000;
        const wasAll = playback.mode === "all";
        stopSpeech();
        seekToRatio(ratio, wasAll);
        if (!wasAll) {
          const { index, offset } = findAtGlobalTime(ratio * trackMeta.totalDuration);
          updateProgressUI(getGlobalTime(index, offset), index);
        }
      });
    }

    $("#btnFont")?.addEventListener("click", () => {
      fontScale = (fontScale + 1) % 3;
      document.body.classList.remove("font-large", "font-xlarge");
      if (fontScale === 1) document.body.classList.add("font-large");
      if (fontScale === 2) document.body.classList.add("font-xlarge");
    });

    $("#voiceSelect")?.addEventListener("change", (e) => {
      selectedVoiceURI = e.target.value;
      localStorage.setItem("vocab_tts_voice", selectedVoiceURI);
    });
  }

  function waitForVoices() {
    return new Promise((resolve) => {
      const v = getEnVoices();
      if (v.length) {
        resolve();
        return;
      }
      synth.onvoiceschanged = () => resolve();
      setTimeout(resolve, 800);
    });
  }

  async function initIndex() {
    manifest = await loadJson("data/manifest.json");
    renderIndex();
  }

  async function initUnit() {
    const params = new URLSearchParams(location.search);
    unitNum = params.get("u") || "1";
    audioBase = `audio/unit-${unitPadded(unitNum)}/`;

    manifest = await loadJson("data/manifest.json");
    const units = await loadJson("data/units.json");
    currentWords = (units[String(unitNum)] || []).map((w) => ({
      ...w,
      sense_in_unit: (w.gloss_zh || "").split("；")[0].split(";")[0].slice(0, 100),
    }));
    renderWordList();

    try {
      audioManifest = await loadJson(`${audioBase}manifest.json`);
    } catch {
      audioManifest = null;
    }

    try {
      currentStory = await loadJson(
        `data/stories/unit-${unitPadded(unitNum)}.json`
      );
    } catch {
      currentStory = null;
    }

    await waitForVoices();
    renderUnit();
    bindUnitPage();
  }

  if ($("#unitList")) {
    initIndex().catch((e) => {
      $("#unitList").innerHTML = `<li class="status">加载失败：${e.message}</li>`;
    });
  } else if ($("#storyBody")) {
    initUnit().catch((e) => {
      $("#storyBody").innerHTML = `<p class="status">加载失败：${e.message}</p>`;
    });
  }
})();
