import { projectLogo } from "../logoData";

export function AboutPage() {
  return (
    <section className="about-project-page" style={{ display: "block" }}>
      <div className="about-project-hero">
        <div className="about-project-hero-main">
          <img className="about-project-logo" src={projectLogo} alt="Дядя Влад" />
          <div className="about-project-hero-copy">
            <div className="about-project-kicker">О ПРОЕКТЕ</div>
            <h1>Дядя Влад читает новости</h1>
            <p className="about-project-lead">Система управления контентом, которая помогает собрать работу с новостями в одном месте — от получения исходного материала до готовой публикации в канале.</p>
          </div>
        </div>
        <div className="about-project-slogan">От новости в источнике до готовой публикации — в одном окне.</div>
      </div>

      <div className="about-project-grid">
        <article className="about-card about-card-intro">
          <div>
            <span className="about-card-label">Что это</span>
            <h2>Рабочее место редактора</h2>
            <p>Система собирает публикации из подключённых источников, помогает отобрать нужные материалы, подготовить текст и медиа, согласовать публикацию и отправить её сразу или по расписанию.</p>
          </div>
        </article>

        <article className="about-card">
          <span className="about-card-label">Уже работает</span>
          <h2>Основные возможности</h2>
          <div className="about-feature-list">
            <div><b>01</b><span>Сбор новостей из подключённых источников</span></div>
            <div><b>02</b><span>Распределение материалов по нужным каналам</span></div>
            <div><b>03</b><span>Редакционная очередь и работа с несколькими каналами</span></div>
            <div><b>04</b><span>Редактирование текста, подписи, фотографий и видео</span></div>
            <div><b>05</b><span>Согласование и отклонение публикаций</span></div>
            <div><b>06</b><span>Публикация в MAX сразу или в выбранное время</span></div>
            <div><b>07</b><span>Архив опубликованных и отклонённых материалов</span></div>
          </div>
        </article>

        <article className="about-card about-roadmap-card">
          <div className="about-roadmap-head">
            <div>
              <span className="about-card-label">Roadmap</span>
              <h2>Куда развивается проект</h2>
            </div>
            <span className="about-roadmap-badge">Следующие этапы</span>
          </div>
          <div className="about-roadmap">
            <div className="about-roadmap-item"><span className="about-roadmap-dot"/><div><strong>ИИ для подготовки текстов</strong><p>Автоматический рерайт новостей с возможностью задавать стиль и правила для каждого канала.</p></div></div>
            <div className="about-roadmap-item"><span className="about-roadmap-dot"/><div><strong>Пользователи и роли</strong><p>Отдельный вход в систему и разделение прав между редакторами, модераторами и администраторами.</p></div></div>
            <div className="about-roadmap-item"><span className="about-roadmap-dot"/><div><strong>Больше источников</strong><p>Подключение Telegram, MAX и других площадок в качестве источников новостей.</p></div></div>
            <div className="about-roadmap-item"><span className="about-roadmap-dot"/><div><strong>Больше площадок для публикации</strong><p>Расширение системы так, чтобы один подготовленный материал можно было отправлять в разные социальные сети и каналы.</p></div></div>
            <div className="about-roadmap-item"><span className="about-roadmap-dot"/><div><strong>Развитие работы с видео</strong><p>Больше автоматизации при получении, подготовке и публикации видеоматериалов.</p></div></div>
          </div>
        </article>
      </div>

      <div className="about-project-footer-note">
        <strong>Задача проекта</strong>
        <span>Сократить ручную работу и дать редактору понятный путь: найти новость → подготовить → согласовать → опубликовать.</span>
      </div>
    </section>
  );
}
