import { ReactNode } from "react";
import "./SectionCard.css";

interface SectionCardProps {
  title: string;
  description?: string;
  children: ReactNode;
}

const SectionCard = ({ title, description, children }: SectionCardProps) => {
  return (
    <section className="section-card">
      <header>
        <h3>{title}</h3>
        {description && <p>{description}</p>}
      </header>
      <div className="section-body">{children}</div>
    </section>
  );
};

export default SectionCard;
