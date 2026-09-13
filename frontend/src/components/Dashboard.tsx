import { Bot } from "lucide-react";

type DashboardProps = {
  activeTargets: number;
  totalTargets: number;
  activeSources: number;
  totalSources: number;
  activeQueue: number;
  totalQueue: number;
};

export function Dashboard({
  activeTargets,
  totalTargets,
  activeSources,
  totalSources,
  activeQueue,
  totalQueue,
}: DashboardProps) {
  return (
    <section className="dashboard-grid">
      <article className="metric"><span>Активные каналы</span><strong>{activeTargets}</strong><small>из {totalTargets}</small></article>
      <article className="metric"><span>Источники</span><strong>{activeSources}</strong><small>из {totalSources}</small></article>
      <article className="metric"><span>В работе</span><strong>{activeQueue}</strong><small>из {totalQueue} материалов</small></article>
      <article className="hero-card"><Bot size={24}/><div><h3>Рерайт подключим следующим этапом</h3><p>Сейчас прототип уже собирает посты и фото, раскладывает по каналам и даёт редактору управлять очередью.</p></div></article>
    </section>
  );
}
