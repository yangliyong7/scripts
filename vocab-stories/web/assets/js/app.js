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
  let playAllQueue = null;
  let fontScale = 0;
  let selectedVoiceURI = localStorage.getItem("vocab_tts_voice") || "";

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

  function stopSpeech() {
    if (synth.speaking) synth.cancel();
    if (htmlAudio) {
      htmlAudio.pause();
      htmlAudio.currentTime = 0;
      htmlAudio = null;
    }
    playAllQueue = null;
    $("#btnPlay")?.classList.remove("hidden");
    $("#btnStop")?.classList.add("hidden");
    $$(".btn-play-part.playing").forEach((b) => b.classList.remove("playing"));
  }

  function showPlaying() {
    $("#btnPlay")?.classList.add("hidden");
    $("#btnStop")?.classList.remove("hidden");
  }

  function speakTextBrowser(text, onEnd) {
    if (!canSpeak || !text.trim()) return false;
    stopSpeech();
    const u = new SpeechSynthesisUtterance(text);
    const voice = pickVoice();
    if (voice) {
      u.voice = voice;
      u.lang = voice.lang || "en-US";
    } else {
      u.lang = "en-US";
    }
    u.rate = 0.9;
    u.pitch = 1;
    u.onend = () => {
      $("#btnPlay")?.classList.remove("hidden");
      $("#btnStop")?.classList.add("hidden");
      if (onEnd) onEnd();
    };
    u.onerror = () => {
      stopSpeech();
    };
    showPlaying();
    synth.speak(u);
    return true;
  }

  function audioUrl(partId) {
    return `${audioBase}part-${partId}.mp3`;
  }

  function playAudioFile(url, onEnd) {
    return new Promise((resolve, reject) => {
      stopSpeech();
      htmlAudio = new Audio(url);
      showPlaying();
      htmlAudio.addEventListener("ended", () => {
        htmlAudio = null;
        if (onEnd) onEnd();
        resolve();
      });
      htmlAudio.addEventListener("error", () => {
        htmlAudio = null;
        reject(new Error("audio load failed: " + url));
      });
      htmlAudio.play().catch(reject);
    });
  }

  async function playPart(partId) {
    const url = audioUrl(partId);
    if (hasNeuralAudio() && audioManifest.parts.some((p) => p.id === partId)) {
      try {
        $$(".btn-play-part.playing").forEach((b) => b.classList.remove("playing"));
        const btn = $(`.btn-play-part[data-part="${partId}"]`);
        btn?.classList.add("playing");
        await playAudioFile(url, () => {
          btn?.classList.remove("playing");
          $("#btnPlay")?.classList.remove("hidden");
          $("#btnStop")?.classList.add("hidden");
        });
        return;
      } catch (e) {
        console.warn("Neural audio failed, fallback to browser TTS", e);
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

  async function playAllParts() {
    if (hasNeuralAudio()) {
      stopSpeech();
      showPlaying();
      playAllQueue = [...audioManifest.parts];
      for (const p of playAllQueue) {
        if (!playAllQueue) break;
        try {
          await playAudioFile(audioUrl(p.id));
        } catch {
          break;
        }
      }
      playAllQueue = null;
      stopSpeech();
      return;
    }
    const all = $$(".story-part")
      .map((el) => stripHtml(el.querySelector(".story")?.innerHTML || ""))
      .filter(Boolean)
      .join("\n\n");
    speakTextBrowser(all);
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
    sel.classList.toggle("hidden", hasNeuralAudio());
  }

  function renderUnit() {
    const meta = manifest.find((m) => String(m.unit) === String(unitNum));
    const title = meta ? meta.label : "Unit " + unitNum;
    $("#pageTitle").textContent = "Unit " + unitPadded(unitNum);
    $("#unitLabel").textContent = title;
    updateAudioModeBadge();
    populateVoiceSelect();

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
  }

  function bindUnitPage() {
    $("#btnBack")?.addEventListener("click", () => {
      location.href = "index.html";
    });
    $("#btnWords")?.addEventListener("click", openDrawer);
    $("#btnCloseDrawer")?.addEventListener("click", closeDrawer);
    $(".drawer-backdrop")?.addEventListener("click", closeDrawer);

    $("#btnPlay")?.addEventListener("click", () => {
      const partId = getVisiblePartId();
      if (hasNeuralAudio()) {
        playPart(partId);
        return;
      }
      if (!canSpeak) {
        alert("暂无神经美音文件，且当前浏览器不支持朗读。请用 Chrome / Edge / Safari。");
        return;
      }
      const ensureVoices = () => {
        const partEl = $(`.story-part[data-part="${partId}"]`);
        const text = stripHtml(partEl?.querySelector(".story")?.innerHTML || "");
        speakTextBrowser(text);
      };
      if (getEnVoices().length === 0) {
        synth.onvoiceschanged = ensureVoices;
      } else {
        ensureVoices();
      }
    });

    $("#btnStop")?.addEventListener("click", stopSpeech);

    $("#btnPlayAll")?.addEventListener("click", () => playAllParts());

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
