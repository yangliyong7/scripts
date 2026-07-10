const STORAGE_KEY = "vocab-learn-progress-v1";
const DAILY_GOAL = 20;

/** @type {{ items: Array<{id:number,word:string,meaning:string,fullMeaning:string,image:string}> }} */
let vocab = { items: [] };

let learnQueue = [];
let learnIndex = 0;
let quizItem = null;
let quizAnswered = false;
let quizPoints = 0;

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

function getProgress() {
  const raw = loadProgress();
  const base = defaultProgress();
  const merged = { ...base, ...raw, today: { ...base.today, ...raw.today } };
  if (merged.today.date !== todayKey()) {
    const yesterday = merged.today.date;
    if (yesterday && merged.today.count > 0) {
      const d1 = new Date(yesterday);
      const d2 = new Date(todayKey());
      const diff = (d2 - d1) / 86400000;
      merged.streak = diff === 1 ? (merged.streak || 0) + 1 : merged.streak;
    }
    merged.today = { date: todayKey(), count: 0 };
  }
  return merged;
}

function bumpToday() {
  const p = getProgress();
  p.today.count += 1;
  p.lastStudyDate = todayKey();
  if (p.today.count === 1 && p.lastStudyDate) {
    // first card today
  }
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

function switchView(name, evt) {
  $$(".view").forEach((v) => v.classList.toggle("active", v.dataset.view === name));
  $$(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
  if (name === "learn") startLearn();
  if (name === "quiz") startQuiz();
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
  $("#learnImage").src = item.image;
  $("#learnImageBack").src = item.image;
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

function startQuiz() {
  quizPoints = 0;
  $("#quizScore").textContent = "0 分";
  pickQuiz();
}

function pickQuiz() {
  quizAnswered = false;
  $("#btnNextQuiz").hidden = true;
  quizItem = vocab.items[Math.floor(Math.random() * vocab.items.length)];
  $("#quizImage").src = quizItem.image;

  const wrong = shuffle(vocab.items.filter((i) => i.word !== quizItem.word)).slice(0, 3);
  const options = shuffle([quizItem, ...wrong]);
  const box = $("#quizOptions");
  box.innerHTML = "";
  options.forEach((opt) => {
    const btn = document.createElement("button");
    btn.className = "option-btn";
    btn.type = "button";
    btn.textContent = opt.word;
    btn.addEventListener("click", () => answerQuiz(btn, opt.word));
    box.appendChild(btn);
  });
}

function answerQuiz(btn, word) {
  if (quizAnswered) return;
  quizAnswered = true;
  const correct = word === quizItem.word;
  $$(".option-btn").forEach((b) => {
    b.disabled = true;
    if (b.textContent === quizItem.word) b.classList.add("correct");
  });
  if (!correct) btn.classList.add("wrong");
  if (correct) {
    quizPoints += 10;
    markWord(quizItem.word, "learned");
    bumpToday();
    toast("回答正确 +10");
  } else {
    toast(`正确答案：${quizItem.word}`);
  }
  $("#quizScore").textContent = `${quizPoints} 分`;
  $("#btnNextQuiz").hidden = false;
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
          <img src="${item.image}" alt="${item.word}" loading="lazy" />
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
  $("#modalImage").src = item.image;
  $("#modalWord").textContent = item.word;
  $("#modalMeaning").textContent = item.fullMeaning || item.meaning;
  $("#wordModal").dataset.word = word;
  $("#wordModal").showModal();
}

async function init() {
  try {
    const res = await fetch("data.json");
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

  if (!vocab.items.length) {
    toast("还没有已配图的单词");
  }

  refreshStats();

  $$("[data-go]").forEach((btn) => {
    btn.addEventListener("click", () => switchView(btn.dataset.go));
  });
  $$("[data-tab]").forEach((btn) => {
    btn.addEventListener("click", (e) => switchView(btn.dataset.tab, e));
  });
  $$("[data-back]").forEach((btn) => {
    btn.addEventListener("click", () => switchView("home"));
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

  $("#btnNextQuiz").addEventListener("click", pickQuiz);
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
}

init();
