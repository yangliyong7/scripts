const STORAGE_KEY = "vocab-learn-progress-v1";
const DAILY_GOAL = 20;

/** @type {{ items: Array<{id:number,word:string,meaning:string,fullMeaning:string,image:string}> }} */
let vocab = { items: [] };
/** @type {{ passages: Array<any> }} */
let clozeData = { passages: [] };

let learnQueue = [];
let learnIndex = 0;
let clozeIndex = 0;
let clozeShowAnswer = false;

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => [...document.querySelectorAll(sel)];

function loadProgress() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
  } catch {
    return {};
  }
}

function saveProgress(data) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
}

function defaultProgress() {
  return {
    learned: {},
    mastered: {},
    today: { date: todayKey(), count: 0 },
    streak: 0,
    lastStudyDate: "",
  };
}

function todayKey() {
  return new Date().toISOString().slice(0, 10);
}

function dayDiff(a, b) {
  const d1 = new Date(`${a}T00:00:00`);
  const d2 = new Date(`${b}T00:00:00`);
  return Math.round((d2 - d1) / 86400000);
}

function getProgress() {
  const raw = loadProgress();
  const base = defaultProgress();
  const merged = { ...base, ...raw, today: { ...base.today, ...raw.today } };
  const today = todayKey();
  if (merged.today.date !== today) {
    merged.today = { date: today, count: 0 };
  }
  // 超过一天没学，连击清零（展示与存储一致）
  if (merged.lastStudyDate) {
    const gap = dayDiff(merged.lastStudyDate, today);
    if (gap > 1) merged.streak = 0;
  } else {
    merged.streak = 0;
  }
  return merged;
}

function bumpToday() {
  const p = getProgress();
  const today = todayKey();
  const firstToday = p.today.count === 0;
  p.today.count += 1;
  if (firstToday) {
    const last = p.lastStudyDate;
    if (!last || last === today) {
      p.streak = Math.max(1, p.streak || 0);
      if (!last) p.streak = 1;
    } else {
      const gap = dayDiff(last, today);
      p.streak = gap === 1 ? (p.streak || 0) + 1 : 1;
    }
  }
  p.lastStudyDate = today;
  saveProgress(p);
  refreshStats();
}

function markWord(word, type) {
  const p = getProgress();
  if (type === "learned") p.learned[word] = Date.now();
  if (type === "mastered") {
    p.mastered[word] = Date.now();
    p.learned[word] = p.learned[word] || Date.now();
  }
  saveProgress(p);
  refreshStats();
  renderLibrary($("#searchInput").value);
}

function shuffle(arr) {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function toast(msg) {
  const el = $("#toast");
  el.textContent = msg;
  el.classList.add("show");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.classList.remove("show"), 2200);
}

function setWordImage(el, item) {
  if (!el || !item) return;
  const fallback = "placeholder.png";
  el.src = item.image || fallback;
  el.onerror = () => {
    if (!el.src.endsWith(fallback)) el.src = fallback;
  };
}

function switchView(name, evt) {
  $$(".view").forEach((v) => v.classList.toggle("active", v.dataset.view === name));
  $$(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
  if (name === "learn") startLearn();
  if (name === "cloze") startCloze();
  if (name === "library") renderLibrary();
  requestAnimationFrame(() => {
    updateTabIndicator();
    if (evt) spawnTabRipple(evt);
  });
}

function updateTabIndicator() {
  const bar = $("#tabbar");
  const indicator = $("#tabIndicator");
  const active = $(".tab.active");
  if (!bar || !indicator || !active) return;
  const barRect = bar.getBoundingClientRect();
  const tabRect = active.getBoundingClientRect();
  indicator.style.width = `${tabRect.width}px`;
  indicator.style.height = `${tabRect.height}px`;
  indicator.style.transform = `translate(${tabRect.left - barRect.left}px, ${tabRect.top - barRect.top}px)`;
}

function spawnTabRipple(evt) {
  const bar = $("#tabbar");
  if (!bar) return;
  const rect = bar.getBoundingClientRect();
  const x = (evt.clientX ?? rect.left + rect.width / 2) - rect.left;
  const y = (evt.clientY ?? rect.top + rect.height / 2) - rect.top;
  [0, 0.1, 0.22].forEach((delay) => {
    const wave = document.createElement("span");
    wave.className = "tab-wave";
    wave.style.left = `${x}px`;
    wave.style.top = `${y}px`;
    wave.style.animationDelay = `${delay}s`;
    bar.appendChild(wave);
    wave.addEventListener("animationend", () => wave.remove());
  });
}

function refreshStats() {
  const p = getProgress();
  const total = vocab.items.length;
  const learned = Object.keys(p.learned).filter((w) => vocab.items.some((i) => i.word === w)).length;
  const mastered = Object.keys(p.mastered).filter((w) => vocab.items.some((i) => i.word === w)).length;

  $("#statTotal").textContent = total;
  $("#statLearned").textContent = learned;
  $("#statMastered").textContent = mastered;
  $("#todayCount").textContent = p.today.count;
  $("#todayGoal").textContent = DAILY_GOAL;
  $("#streakBadge").textContent = `✦ ${p.streak || 0}`;
  $("#streakBadge").title = p.streak ? `已连续学习 ${p.streak} 天` : "连续学习天数：今天学过会开始累计";

  const pct = Math.min(1, p.today.count / DAILY_GOAL);
  const ring = $("#progressRing");
  const circumference = 327;
  if (ring) ring.style.strokeDashoffset = String(circumference * (1 - pct));

  if (p.today.count >= DAILY_GOAL) {
    $("#heroTip").textContent = "今日目标已达成，太棒了！";
  } else {
    $("#heroTip").textContent = `还差 ${DAILY_GOAL - p.today.count} 个词完成今日目标`;
  }
}

function startLearn() {
  const p = getProgress();
  const unlearned = vocab.items.filter((i) => !p.learned[i.word]);
  learnQueue = shuffle(unlearned.length ? unlearned : vocab.items);
  learnIndex = 0;
  showLearnCard();
}

function showLearnCard() {
  const card = $("#flashcard");
  card.classList.remove("flipped");
  const item = learnQueue[learnIndex];
  if (!item) {
    toast("本轮学习完成");
    switchView("home");
    return;
  }
  setWordImage($("#learnImage"), item);
  setWordImage($("#learnImageBack"), item);
  $("#learnWord").textContent = item.word;
  $("#learnMeaning").textContent = item.fullMeaning || item.meaning;
  $("#learnProgress").textContent = `${learnIndex + 1}/${learnQueue.length}`;
}

function nextLearn(step) {
  const item = learnQueue[learnIndex];
  if (step === "know") markWord(item.word, "learned");
  bumpToday();
  learnIndex += 1;
  if (learnIndex >= learnQueue.length) {
    toast("本轮卡片学完啦");
    switchView("home");
    return;
  }
  showLearnCard();
}

function renderLibrary(filter = "") {
  const p = getProgress();
  const q = filter.trim().toLowerCase();
  const list = vocab.items.filter((item) => {
    if (!q) return true;
    return item.word.includes(q) || item.meaning.includes(q) || (item.fullMeaning || "").includes(q);
  });

  $("#libCount").textContent = String(list.length);
  const box = $("#wordList");
  if (!list.length) {
    box.innerHTML = `<div class="empty-state"><strong>暂无匹配词汇</strong>试试其他关键词</div>`;
    return;
  }

  box.innerHTML = list
    .map((item) => {
      const mastered = p.mastered[item.word];
      const learned = p.learned[item.word];
      const tag = mastered ? '<span class="tag mastered">掌握</span>' : learned ? '<span class="tag">已学</span>' : "";
      return `
        <article class="word-item" data-word="${item.word}">
          <img src="${item.image || "placeholder.png"}" alt="${item.word}" loading="lazy" onerror="this.onerror=null;this.src='placeholder.png'" />
          <div class="meta">
            <strong>${item.word}</strong>
            <span>${item.meaning}</span>
          </div>
          ${tag}
        </article>`;
    })
    .join("");

  box.querySelectorAll(".word-item").forEach((el) => {
    el.addEventListener("click", () => openModal(el.dataset.word));
  });
}

function openModal(word) {
  const item = vocab.items.find((i) => i.word === word);
  if (!item) return;
  setWordImage($("#modalImage"), item);
  $("#modalWord").textContent = item.word;
  $("#modalMeaning").textContent = item.fullMeaning || item.meaning;
  $("#wordModal").dataset.word = word;
  $("#wordModal").showModal();
}

function startCloze() {
  if (!clozeData.passages?.length) {
    toast("暂无听写题库，请先运行 build_cloze_data.py");
    return;
  }
  clozeShowAnswer = false;
  if (clozeIndex < 0 || clozeIndex >= clozeData.passages.length) clozeIndex = 0;
  renderCloze();
  // 进入时自动朗读
  setTimeout(() => speakCloze(), 350);
}

function renderCloze() {
  const p = clozeData.passages[clozeIndex];
  if (!p) return;
  $("#clozeProgress").textContent = `${clozeIndex + 1}/${clozeData.passages.length}`;
  const box = $("#clozePassage");
  const parts = [];
  if (p.title) {
    parts.push(`<div class="cloze-title">${escapeHtml(p.title)}</div>`);
  }
  p.segments.forEach((seg) => {
    if (seg.type === "text") {
      parts.push(`<span class="cloze-text">${escapeHtml(seg.value)}</span>`);
      return;
    }
    const blank = p.blanks[seg.index];
    const word = blank?.word || "";
    const hint = blank?.hint || "";
    if (clozeShowAnswer) {
      parts.push(
        `<span class="cloze-answer" title="${escapeHtml(hint)}">${escapeHtml(word)}</span>` +
          `<span class="cloze-hint">（${escapeHtml(hint)}）</span>`
      );
    } else {
      parts.push(
        `<span class="cloze-blank-wrap">` +
          `<input class="cloze-input" data-index="${seg.index}" data-answer="${escapeAttr(word)}" ` +
          `spellcheck="false" autocomplete="off" autocapitalize="off" size="${Math.max(word.length, 6)}" />` +
          `<span class="cloze-hint">（${escapeHtml(hint)}）</span>` +
          `</span>`
      );
    }
  });
  box.innerHTML = parts.join("");
  if (!clozeShowAnswer) {
    box.querySelectorAll(".cloze-input").forEach((input) => {
      input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          checkClozeInput(input);
          focusNextBlank(input);
        }
      });
      input.addEventListener("blur", () => checkClozeInput(input));
    });
    const first = box.querySelector(".cloze-input");
    if (first) first.focus();
  }
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function escapeAttr(s) {
  return escapeHtml(s).replaceAll("'", "&#39;");
}

function checkClozeInput(input) {
  const ok = input.value.trim().toLowerCase() === (input.dataset.answer || "").toLowerCase();
  input.classList.toggle("ok", ok && input.value.trim() !== "");
  input.classList.toggle("bad", !ok && input.value.trim() !== "");
}

function focusNextBlank(current) {
  const inputs = [...$$(".cloze-input")];
  const i = inputs.indexOf(current);
  if (i >= 0 && i < inputs.length - 1) inputs[i + 1].focus();
}

function pickVoice(langPrefix) {
  const voices = window.speechSynthesis.getVoices();
  return (
    voices.find((v) => v.lang.toLowerCase().startsWith(langPrefix) && /neural|online|premium/i.test(v.name)) ||
    voices.find((v) => v.lang.toLowerCase().startsWith(langPrefix)) ||
    null
  );
}

function speakCloze() {
  const p = clozeData.passages[clozeIndex];
  if (!p?.segments?.length) return;
  if (!window.speechSynthesis) {
    toast("当前浏览器不支持朗读");
    return;
  }
  stopSpeak();

  // 先念故事标题，再顺读中文；挖空处念对应英文单词
  const queue = [];
  if (p.title) queue.push({ text: p.title, lang: "zh-CN", rate: 1 });
  p.segments.forEach((seg) => {
    if (seg.type === "text") {
      const text = (seg.value || "").trim();
      if (text) queue.push({ text, lang: "zh-CN", rate: 1 });
      return;
    }
    const word = p.blanks[seg.index]?.word;
    if (word) queue.push({ text: word, lang: "en-US", rate: 0.85 });
  });
  if (!queue.length) return;

  let i = 0;
  const next = () => {
    if (i >= queue.length) return;
    const item = queue[i++];
    const u = new SpeechSynthesisUtterance(item.text);
    u.lang = item.lang;
    u.rate = item.rate;
    const voice = pickVoice(item.lang.slice(0, 2));
    if (voice) u.voice = voice;
    u.onend = next;
    u.onerror = next;
    window.speechSynthesis.speak(u);
  };
  next();
}

function stopSpeak() {
  if (window.speechSynthesis) window.speechSynthesis.cancel();
}

function clozePrev() {
  stopSpeak();
  clozeShowAnswer = false;
  clozeIndex = (clozeIndex - 1 + clozeData.passages.length) % clozeData.passages.length;
  renderCloze();
  speakCloze();
}

function clozeNext() {
  stopSpeak();
  clozeShowAnswer = false;
  clozeIndex = (clozeIndex + 1) % clozeData.passages.length;
  bumpToday();
  renderCloze();
  speakCloze();
}

function clozeToggleAnswer() {
  clozeShowAnswer = !clozeShowAnswer;
  renderCloze();
  if (clozeShowAnswer) {
    const p = clozeData.passages[clozeIndex];
    p?.blanks?.forEach((b) => markWord(b.word, "learned"));
  }
}

async function init() {
  try {
    const res = await fetch(`data.json?v=${Date.now()}`, { cache: "no-store" });
    if (!res.ok) throw new Error("data.json missing");
    vocab = await res.json();
  } catch (e) {
    $(".app").innerHTML = `
      <div class="empty-state" style="padding:60px 24px">
        <strong>暂无词汇数据</strong>
        <p>请先在 ReleasePlanCheck 目录运行：<br><code>py build_vocab_data.py</code></p>
      </div>`;
    return;
  }

  try {
    const cres = await fetch(`cloze.json?v=${Date.now()}`, { cache: "no-store" });
    if (cres.ok) clozeData = await cres.json();
  } catch {
    clozeData = { passages: [] };
  }

  // 预热 TTS 语音列表
  if (window.speechSynthesis) {
    window.speechSynthesis.getVoices();
    window.speechSynthesis.onvoiceschanged = () => window.speechSynthesis.getVoices();
  }

  if (!vocab.items.length) {
    toast("词库为空，请先生成 data.json");
  }

  refreshStats();

  $$("[data-go]").forEach((btn) => {
    btn.addEventListener("click", () => switchView(btn.dataset.go));
  });
  $$("[data-tab]").forEach((btn) => {
    btn.addEventListener("click", (e) => switchView(btn.dataset.tab, e));
  });
  $$("[data-back]").forEach((btn) => {
    btn.addEventListener("click", () => {
      stopSpeak();
      switchView("home");
    });
  });

  updateTabIndicator();
  window.addEventListener("resize", updateTabIndicator);

  $("#flashcard").addEventListener("click", () => $("#flashcard").classList.toggle("flipped"));
  $("#btnFlip").addEventListener("click", (e) => {
    e.stopPropagation();
    $("#flashcard").classList.toggle("flipped");
  });
  $("#btnKnow").addEventListener("click", (e) => {
    e.stopPropagation();
    nextLearn("know");
  });
  $("#btnAgain").addEventListener("click", (e) => {
    e.stopPropagation();
    learnQueue.push(learnQueue[learnIndex]);
    nextLearn("again");
  });

  $("#searchInput").addEventListener("input", (e) => renderLibrary(e.target.value));

  $("#modalClose").addEventListener("click", () => $("#wordModal").close());
  $("#modalMarkLearned").addEventListener("click", () => {
    markWord($("#wordModal").dataset.word, "learned");
    toast("已标记为已学");
    $("#wordModal").close();
  });
  $("#modalMarkMastered").addEventListener("click", () => {
    markWord($("#wordModal").dataset.word, "mastered");
    toast("已标记为掌握");
    $("#wordModal").close();
  });

  $("#btnClozePrev")?.addEventListener("click", clozePrev);
  $("#btnClozeNext")?.addEventListener("click", clozeNext);
  $("#btnClozeSpeak")?.addEventListener("click", speakCloze);
  $("#btnClozeAnswer")?.addEventListener("click", clozeToggleAnswer);

  window.addEventListener("keydown", (e) => {
    if (!$("#view-cloze")?.classList.contains("active")) return;
    if (e.target.matches("input, textarea")) {
      if (e.ctrlKey && (e.key === "a" || e.key === "A")) {
        e.preventDefault();
        speakCloze();
      }
      return;
    }
    if (e.key === "ArrowLeft") clozePrev();
    if (e.key === "ArrowRight") clozeNext();
    if (e.key === "ArrowUp" || e.key === "ArrowDown") {
      e.preventDefault();
      clozeToggleAnswer();
    }
    if (e.ctrlKey && (e.key === "a" || e.key === "A")) {
      e.preventDefault();
      speakCloze();
    }
  });
}

init();
