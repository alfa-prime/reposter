export {};

const ABOUT_ACTIVE_CLASS = "about-project-active";

function aboutIcon() {
  return `
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="10"/>
      <path d="M12 16v-4"/>
      <path d="M12 8h.01"/>
    </svg>
  `;
}

function closeAbout() {
  const workspace = document.querySelector<HTMLElement>(".workspace");
  const button = document.querySelector<HTMLButtonElement>(".about-nav-button");
  workspace?.classList.remove(ABOUT_ACTIVE_CLASS);
  button?.classList.remove("active");
}

function openAbout() {
  const workspace = document.querySelector<HTMLElement>(".workspace");
  const button = document.querySelector<HTMLButtonElement>(".about-nav-button");
  if (!workspace) return;
  workspace.classList.add(ABOUT_ACTIVE_CLASS);
  button?.classList.add("active");
  workspace.querySelector<HTMLElement>(".about-project-page")?.scrollTo({ top: 0 });
}

function createAboutPage(workspace: HTMLElement) {
  if (workspace.querySelector(".about-project-page")) return;

  const page = document.createElement("section");
  page.className = "about-project-page";
  page.innerHTML = `
    <div class="about-project-hero">
      <div class="about-project-kicker">О ПРОЕКТЕ</div>
      <h1>Дядя Влад читает новости</h1>
      <p class="about-project-lead">Система управления контентом, которая помогает собрать работу с новостями в одном месте — от получения исходного материала до готовой публикации в канале.</p>
      <div class="about-project-slogan">От новости в источнике до готовой публикации — в одном окне.</div>
    </div>

    <div class="about-project-grid">
      <article class="about-card about-card-intro">
        <div class="about-card-icon">✦</div>
        <div>
          <span class="about-card-label">Что это</span>
          <h2>Рабочее место редактора</h2>
          <p>Система собирает публикации из подключённых источников, помогает отобрать нужные материалы, подготовить текст и медиа, согласовать публикацию и отправить её сразу или по расписанию.</p>
        </div>
      </article>

      <article class="about-card">
        <span class="about-card-label">Уже работает</span>
        <h2>Основные возможности</h2>
        <div class="about-feature-list">
          <div><b>01</b><span>Сбор новостей из подключённых источников</span></div>
          <div><b>02</b><span>Распределение материалов по нужным каналам</span></div>
          <div><b>03</b><span>Редакционная очередь и работа с несколькими каналами</span></div>
          <div><b>04</b><span>Редактирование текста, подписи, фотографий и видео</span></div>
          <div><b>05</b><span>Согласование и отклонение публикаций</span></div>
          <div><b>06</b><span>Публикация в MAX сразу или в выбранное время</span></div>
          <div><b>07</b><span>Архив опубликованных и отклонённых материалов</span></div>
        </div>
      </article>

      <article class="about-card about-roadmap-card">
        <div class="about-roadmap-head">
          <div>
            <span class="about-card-label">Roadmap</span>
            <h2>Куда развивается проект</h2>
          </div>
          <span class="about-roadmap-badge">Следующие этапы</span>
        </div>
        <div class="about-roadmap">
          <div class="about-roadmap-item">
            <span class="about-roadmap-dot"></span>
            <div><strong>ИИ для подготовки текстов</strong><p>Автоматический рерайт новостей с возможностью задавать стиль и правила для каждого канала.</p></div>
          </div>
          <div class="about-roadmap-item">
            <span class="about-roadmap-dot"></span>
            <div><strong>Пользователи и роли</strong><p>Отдельный вход в систему и разделение прав между редакторами, модераторами и администраторами.</p></div>
          </div>
          <div class="about-roadmap-item">
            <span class="about-roadmap-dot"></span>
            <div><strong>Больше источников</strong><p>Подключение Telegram, MAX и других площадок в качестве источников новостей.</p></div>
          </div>
          <div class="about-roadmap-item">
            <span class="about-roadmap-dot"></span>
            <div><strong>Больше площадок для публикации</strong><p>Расширение системы так, чтобы один подготовленный материал можно было отправлять в разные социальные сети и каналы.</p></div>
          </div>
          <div class="about-roadmap-item">
            <span class="about-roadmap-dot"></span>
            <div><strong>Развитие работы с видео</strong><p>Больше автоматизации при получении, подготовке и публикации видеоматериалов.</p></div>
          </div>
        </div>
      </article>
    </div>

    <div class="about-project-footer-note">
      <strong>Задача проекта</strong>
      <span>Сократить ручную работу и дать редактору понятный путь: найти новость → подготовить → согласовать → опубликовать.</span>
    </div>
  `;

  workspace.append(page);
}

function install() {
  const nav = document.querySelector<HTMLElement>(".sidebar nav");
  const workspace = document.querySelector<HTMLElement>(".workspace");
  if (!nav || !workspace) return;

  createAboutPage(workspace);

  let button = nav.querySelector<HTMLButtonElement>(".about-nav-button");
  if (!button) {
    button = document.createElement("button");
    button.type = "button";
    button.className = "about-nav-button";
    button.innerHTML = `${aboutIcon()}<span>О проекте</span>`;
    button.addEventListener("click", openAbout);
    nav.append(button);
  }

  nav.querySelectorAll<HTMLButtonElement>("button:not(.about-nav-button)").forEach((navButton) => {
    if (navButton.dataset.aboutCloseBound === "true") return;
    navButton.dataset.aboutCloseBound = "true";
    navButton.addEventListener("click", closeAbout);
  });
}

const observer = new MutationObserver(install);
observer.observe(document.documentElement, { childList: true, subtree: true });
install();
