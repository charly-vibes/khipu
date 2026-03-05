# khipu Analysis Report

**Generated:** {{ timestamp }}
**Sessions analysed:** {{ session_count }}{% if sessions_skipped %} ({{ sessions_skipped }} skipped){% endif %}

{% if metadata %}
**Backend:** {{ metadata.backend }} · **Model:** {{ metadata.model }} · **Duration:** {{ metadata.duration_ms }}ms
{% endif %}

---

## Workflows

{% if workflows %}
{% for w in workflows %}
### {{ w.name }}

**Goal:** {{ w.goal }}
**Sessions:** {{ w.session_count }}

**Steps:**
{% for step in w.steps %}
1. {{ step }}
{% endfor %}
{% if w.variants %}

**Variants:**
{% for v in w.variants %}
- {{ v }}
{% endfor %}
{% endif %}

{% endfor %}
{% else %}
_No workflows identified._
{% endif %}

---

## Patterns

{% if patterns %}
{% for p in patterns %}
- **[{{ p.type }}]** {{ p.description }} _(confidence: {{ "%.0f"|format(p.confidence * 100) }}%)_
{% endfor %}
{% else %}
_No patterns identified._
{% endif %}

---

## Crystallization Scores

{% if crystallization %}
| # | Convergence | Stability | Score | Recommendation |
|---|-------------|-----------|-------|----------------|
{% for c in crystallization %}
| {{ loop.index }} | {{ "%.2f"|format(c.convergence) }} | {{ "%.2f"|format(c.stability) }} | **{{ "%.2f"|format(c.score) }}** | {{ c.recommendation }} |
{% endfor %}

{% for c in crystallization %}
{% if c.suggested_implementation %}
**Pattern {{ loop.index }} — Implementation suggestion:** {{ c.suggested_implementation }}
{% endif %}
{% endfor %}
{% else %}
_No crystallization data._
{% endif %}

{% if custom %}
---

## Custom Analyzers

{% for name, items in custom.items() %}
### {{ name }}

```json
{{ items | tojson(indent=2) }}
```

{% endfor %}
{% endif %}
