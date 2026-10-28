import { notFound } from "next/navigation";
import { domainBySlug, DOMAINS } from "@/lib/domains";
import { AgentDomain } from "@/components/AgentDomain";
import { CodeDomain } from "@/components/CodeDomain";
import { DesignDomain } from "@/components/DesignDomain";
import { OsintDomain } from "@/components/OsintDomain";
import { PentestDomain } from "@/components/PentestDomain";

export function generateStaticParams() {
  return DOMAINS.map((d) => ({ domain: d.slug }));
}

export default function DomainPage({ params }: { params: { domain: string } }) {
  const domain = domainBySlug(params.domain);
  if (!domain) notFound();
  if (domain.slug === "code") return <CodeDomain />;
  if (domain.slug === "osint") return <OsintDomain />;
  if (domain.slug === "design") return <DesignDomain />;
  if (domain.slug === "agent") return <AgentDomain />;
  return <PentestDomain />;
}
