import { projectLogo } from "../logoData";
import "../about.css";

export function AboutPage() {
  return (
    <section className="about-project-page" style={{ display: "block" }}>
      <div className="about-project-hero">
        <div className="about-project-hero-main">
          <img className="about-project-logo" src={projectLogo} alt="Дядя Влад" />
          <div className="about-project-hero-copy">
            <div className="about-project-kicker">О ПРОЕКТЕ</div>
            <h1>Дядя Влад читает новости</h1>
            <p className="about-project-lead">Редакционная система, которая сама собирает новости, готовит текст с помощью ИИ и проводит материал через понятный процесс модерации до публикации в канале.</p>
          </div>
        </div>
        <div className="about-project-flow" aria-label="Основной путь новости в системе">
          <span>VK</span><b>→</b><span>GigaChat</span><b>→</b><span>Редактор</span><b>→</b><span>MAX</span>
        </div>
      </div>

      <div className="about-project-grid">
        <article className="about-card about-card-intro">
          <div>
            <span className="about-card-label">Что это</span>
            <h2>Рабочее место редактора</h2>
            <p>Проект объединяет автоматический сбор, ИИ-рерайт, работу с текстом и медиа, модерацию и публикацию. Редактор видит весь путь новости в одном интерфейсе и подключается там, где действительно требуется решение человека.</p>
          </div>
        </article>

        <article className="about-card">
          <span className="about-card-label">Уже работает</span>
          <h2>Основные возможности</h2>
          <div className="about-feature-list">
            <div><b>01</b><span>Автоматический и ручной сбор новых публикаций из активных источников VK</span></div>
            <div><b>02</b><span>Распределение одного материала по подключённым целевым каналам</span></div>
            <div><b>03</b><span>Рерайт через GigaChat по отдельной инструкции для каждого канала</span></div>
            <div><b>04</b><span>Редакционная очередь: хранилище, модерация, расписание и архив</span></div>
            <div><b>05</b><span>Редактирование текста, фотографий, видео и подписи публикации</span></div>
            <div><b>06</b><span>Согласование, отклонение и возврат материала в работу</span></div>
            <div><b>07</b><span>Публикация в MAX сразу или в выбранные дату и время</span></div>
            <div><b>08</b><span>Контроль результата публикации и сохранение понятной причины ошибки</span></div>
          </div>
        </article>

        <article className="about-card about-process-card">
          <span className="about-card-label">Как это работает</span>
          <h2>Путь одной новости</h2>
          <div className="about-process">
            <div><b>1</b><strong>Получить</strong><p>Сборщик находит все новые посты и сохраняет исходный текст и медиа.</p></div>
            <div><b>2</b><strong>Подготовить</strong><p>GigaChat переписывает текст с учётом правил выбранного канала.</p></div>
            <div><b>3</b><strong>Проверить</strong><p>Редактор корректирует материал, подпись и вложения, затем согласовывает его.</p></div>
            <div><b>4</b><strong>Опубликовать</strong><p>Система отправляет пост в MAX сразу или автоматически в назначенное время.</p></div>
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
            <div className="about-roadmap-item"><span className="about-roadmap-dot"/><div><strong>Пользователи и роли</strong><p>Отдельный вход в систему и разделение прав между редакторами, модераторами и администраторами.</p></div></div>
            <div className="about-roadmap-item"><span className="about-roadmap-dot"/><div><strong>Больше источников</strong><p>Подключение Telegram, MAX и других площадок в качестве источников новостей.</p></div></div>
            <div className="about-roadmap-item"><span className="about-roadmap-dot"/><div><strong>Больше площадок для публикации</strong><p>Расширение системы так, чтобы один подготовленный материал можно было отправлять в разные социальные сети и каналы.</p></div></div>
            <div className="about-roadmap-item"><span className="about-roadmap-dot"/><div><strong>Развитие работы с видео</strong><p>Больше автоматизации при получении, подготовке и публикации видеоматериалов.</p></div></div>
            <div className="about-roadmap-item"><span className="about-roadmap-dot"/><div><strong>Аналитика и контроль</strong><p>Статистика по источникам, каналам, публикациям и результатам работы редакции.</p></div></div>
          </div>
        </article>
      </div>

      <div className="about-project-footer-note">
        <strong>Задача проекта</strong>
        <span>Снять с редактора повторяющиеся операции, сохранив за человеком контроль над содержанием и моментом публикации.</span>
      </div>
    </section>
  );
}
