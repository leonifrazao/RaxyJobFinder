from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


_REQUISITO_PATTERNS: list[tuple[str, str]] = [
    (r'\bensino\s*superior\b', 'ensino_superior'),
    (r'\b(graduação|graduacao)\b', 'graduacao'),
    (r'\bforma[cç][aã]o\s*(completa|superior)\b', 'graduacao'),
    (r'\bp[sóó]s[- ]?graduação\b|\bpos[- ]?graduacao\b', 'pos_graduacao'),
    (r'\bmestrado\b', 'mestrado'),
    (r'\bdoutorado\b', 'doutorado'),
    (r'\b(ingl[eê]s|ingles)\s*(avançado|fluente|fluency|intermedi[áa]rio)\b', 'ingles'),
    (r'\bespanhol\s*(avançado|fluente|intermedi[áa]rio)\b', 'espanhol'),
    (r'\bexcel\b', 'excel'),
    (r'\bpython\b', 'python'),
    (r'\bsql\b', 'sql'),
    (r'\bsas\b', 'sas'),
    (r'\bdatabricks\b', 'databricks'),
    (r'\bpyspark\b', 'pyspark'),
    (r'\bspark\b', 'spark'),
    (r'\bteradata\b', 'teradata'),
    (r'\bariba\b', 'ariba'),
    (r'\bpower\s*bi\b', 'power_bi'),
    (r'\btableau\b', 'tableau'),
    (r'\bpacote\s*office\b', 'pacote_office'),
    (r'\bjavascript\b', 'javascript'),
    (r'\btypescript\b', 'typescript'),
    (r'\bjava\b(?!\s*script)', 'java'),
    (r'\bc#\b|\bcsharp\b', 'csharp'),
    (r'\br\b(?=\s*language)', 'r'),
    (r'\bgoogle\s*(sheets|workspace|planilhas)\b', 'google_workspace'),
    (r'\bcomunica[cç][aã]o\b', 'comunicacao'),
    (r'\btrabalho\s*em\s*(equipe|time)\b', 'trabalho_em_equipe'),
    (r'\bproatividade\b|\bproativo\b', 'proatividade'),
    (r'\bracioc[ií]nio\s*l[oó]gico\b', 'raciocinio_logico'),
    (r'\bperfil\s*anal[ií]tico\b|\bpensamento\s*anal[ií]tico\b', 'perfil_analitico'),
    (r'\borganiza[cç][aã]o\b|\borganizado\b', 'organizacao'),
    (r'\blideran[cç]a\b', 'lideranca'),
    (r'\bcriatividade\b|\bcriativo\b', 'criatividade'),
    (r'\bplanejamento\b', 'planejamento'),
    (r'\bno[çc][õo]es?\s*de\s*l[oó]gica\s*de\s*programa[cç][aã]o\b', 'logica_programacao'),
    (r'\bengenharia\s*de\s*dados\b', 'engenharia_dados'),
    (r'\be[tl][tl]\b', 'etl'),
    (r'\bintelig[êe]ncia\s*artificial\b', 'inteligencia_artificial'),
    (r'\bmachine\s*learning\b|\baprendizado\s*de\s*m[aá]quina\b', 'machine_learning'),
    (r'\bpower\s*automate\b|\brpa\b|\bautoma[cç][aã]o\b', 'automacao'),
    (r'\bCI/CD\b|\bdevops\b|\bgit\b', 'devops'),
    (r'\bdocker\b', 'docker'),
    (r'\bkubernetes\b|\bk8s\b', 'kubernetes'),
    (r'\baws\b|\bazure\b|\bgcp\b|\bgoogle\s*cloud\b|\bamazon\s*web\s*services\b', 'cloud'),
    (r'\b[áa]gil\b|\bscrum\b|\bkanban\b', 'metodologias_ageis'),
    (r'\bhtml\b', 'html'),
    (r'\bcss\b', 'css'),
    (r'\breact\b', 'react'),
    (r'\bnode\.?js\b', 'nodejs'),
    (r'\bapi\b|\brest\b', 'api'),
    (r'\bcertifica[cçç][aã]o\b|\bcertifica[cç][aã]o\b|\bcertificado\b', 'certificacao'),
    (r'\b[tT][iI]\b|tecnologia\s*da\s*informa[cç][aã]o', 'ti'),
    (r'\b[dD]ados\b', 'dados'),
    (r'\bfinan[cç]as\b|\bfinanceiro\b', 'financas'),
    (r'\bcont[áa]bil\b|\bcontabilidade\b', 'contabilidade'),
    (r'\bmarketing\b', 'marketing'),
    (r'\bvendas\b|\bcomercial\b', 'vendas'),
    (r'\batuação\s*(cliente|externo)\b|\brelacionamento\s*com\s*cliente\b|\bclientes\b', 'atendimento_cliente'),
    (r'\bnegocia[cç][aã]o\b', 'negociacao'),
    (r'\ban[áa]lise\s*de\s*dados\b|\ban[áa]lise\s*dados\b', 'analise_dados'),
    (r'\b(resolu[cç][aã]o|solu[cç][aã]o)\s*de\s*problemas\b|\bresolver\s*problemas\b', 'resolucao_problemas'),
    (r'\baten[cç][aã]o\s*a\s*detalhes\b|\bdetalhes\b', 'atencao_detalhes'),
    (r'\bautonomia\b|\btrabalho\s*aut[ôo]nomo\b', 'autonomia'),
    (r'\bresponsabilidade\b|\brespons[áa]vel\b', 'responsabilidade'),
    (r'\bfoco\s*em\s*resultados\b|\borienta[cç][aã]o\s*a\s*resultados\b|\bresultados\b', 'foco_resultados'),
    (r'\bempreendedorismo\b|\bpensamento\s*criativo\b|\binova[cç][aã]o\b', 'inovacao'),
    (r'\btomada\s*de\s*decis[aã]o\b', 'tomada_decisao'),
    (r'\bgest[aã]o\s*de\s*tempo\b|\bprioriza[cç][aã]o\b', 'gestao_tempo'),
    (r'\bword\b', 'word'),
    (r'\bpowerpoint\b|\bppt\b', 'powerpoint'),
    (r'\boutlook\b', 'outlook'),
    (r'\bphotoshop\b|\b illustrator\b|\bfigma\b', 'design'),
    (r'\bsap\b', 'sap'),
    (r'\boracle\b', 'oracle'),
    (r'\bpostgres\b|\bpostgresql\b|\bmysql\b|\bmariadb\b|\bmongo(db)?\b|\bredis\b', 'banco_dados'),
    (r'\bdjango\b|\bflask\b|\bfastapi\b', 'framework_python'),
    (r'\bspring\b|\bspring\s*boot\b', 'spring'),
    (r'\bwindows\s*server\b|\blinux\b|\bunix\b', 'sistemas_operacionais'),
    (r'\bredes\s*neurais\b|\bdeep\s*learning\b|\bnlp\b|\bvis[aã]o\s*computacional\b', 'deep_learning'),
    (r'\bseguran[cç]a\s*da\s*informa[cç][aã]o\b|\bciberseguran[cç]a\b|\bcyber\b', 'ciberseguranca'),
    (r'\bregulatório\b|\bregulatorio\b|\bcompliance\b|\blgpd\b', 'regulatorio'),
    (r'\bprazos?\s*(apertados?|curtos?)?\b', 'gestao_prazos'),
    (r'\bDDD\b|\bdomain[- ]driven\s*design\b', 'ddd'),
    (r'\bSOLID\b', 'solid'),
    (r'\barquitetura\s*hexagonal\b|\bhexagonal\s*architecture\b|\bports\s*and\s*adapters\b', 'arquitetura_hexagonal'),
    (r'\bclean\s*arch(itecture)?\b|\barquitetura\s*limpa\b', 'clean_arch'),
    (r'\barquitetura\s*de\s*software\b|\bsoftware\s*architecture\b', 'arquitetura_software'),
    (r'\bmodelagem\s*de\s*dados\b|\bdata\s*modeling\b', 'modelagem_dados'),
    (r'\bpadr[õo]es?\s*de\s*projeto\b|\bdesign\s*patterns?\b', 'design_patterns'),
    (r'\bCQRS\b|\bevent\s*sourcing\b', 'cqrs_event_sourcing'),
    (r'\bmicrosservi[çc]os?\b|\bmicroservices?\b', 'microservicos'),
    (r'\bapi\s*rest(ful)?\b|\bgraphql\b|\bgrpc\b', 'api_rest'),
    (r'\bmessage\s*broker\b|\bfila\s*mensageria\b|\brabbitmq\b|\bkafka\b|\bsqs\b|\bsns\b|\bpub[- ]?sub\b', 'mensageria'),
    (r'\bcontaineriza[cç][aã]o\b|\bcontainers?\b', 'containerizacao'),
    (r'\borquestra[cç][aã]o\b|\borchestration\b', 'orquestracao'),
    (r'\bmonitoramento\b|\bobservabilidade\b|\bprometheus\b|\bgrafana\b|\bdatadog\b|\bnew\s*relic\b|\bopentelemetry\b', 'observabilidade'),
    (r'\bTDD\b|\btest[- ]driven\s*development\b|\bteste\s*unit[áa]rio\b|\bteste\s*de\s*integra[cç][aã]o\b', 'testes'),
    (r'\b(integra[cç][aã]o\s*cont[ií]nua|continuous\s*integration|entrega\s*cont[ií]nua|continuous\s*delivery)\b', 'ci_cd'),
    (r'\bdiagrama\s*de\s*classes?\b|\bUML\b|\bDER\b|\bdiagrama\s*entidade\s*relacionamento\b', 'modelagem_uml'),
    (r'\blinguagem\s*de\s*programa[cç][aã]o\b', 'linguagem_programacao'),
]


def extract_requisitos(description: str) -> list[str]:
    if not description:
        return []
    desc_lower = description.lower()
    found: set[str] = set()
    for pattern, label in _REQUISITO_PATTERNS:
        if re.search(pattern, desc_lower, re.IGNORECASE):
            found.add(label)
    return sorted(found)


@dataclass(frozen=True)
class JobDetails:
    title: str = ""
    company: str = ""
    company_url: str = ""
    location: str = ""
    posted_text: str = ""
    applicants_text: str = ""
    description: str = ""
    criteria: dict[str, Any] = field(default_factory=dict)
    apply_text: str = ""
    url: str = ""
    logo_url: str = ""
    provider_data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = {
            "detail_title": self.title,
            "detail_company": self.company,
            "detail_company_url": self.company_url,
            "detail_location": self.location,
            "detail_posted_text": self.posted_text,
            "detail_applicants_text": self.applicants_text,
            "description": self.description,
            "criteria": self.criteria,
            "apply_text": self.apply_text,
            "detail_url": self.url,
            "detail_logo_url": self.logo_url,
        }
        data.update(self.provider_data)
        return data
