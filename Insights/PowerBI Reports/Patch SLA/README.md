# VM Standard Patch Management — Executive Dashboard

A Power BI report showing server patch compliance and mean time to patch, sourced
directly from HCL BigFix Insights.

Distributed as a **`.pbit` template** — it contains no data. See [Setup](#setup).

---

## What it does

Answers two questions for leadership:

- **Patch Compliance** — what percentage of in-scope servers have no patch
  outstanding beyond the 45-day SLA
- **Mean Time To Patch (MTTP)** — how many days, on average, from a patch being
  released to it being deployed

Both are shown with period-over-period movement, a status indicator against
thresholds, and a breakdown by operating system.

Data can be viewed at **monthly, weekly or yearly** grain, over a trailing 3, 6 or
12 period window, and filtered by OS and BigFix computer group.

| KPI | Target | At risk | Off target |
|---|---|---|---|
| Patch Compliance | ≥ 95% | 90–95% | < 90% |
| Mean Time To Patch | < 40 days | 40–45 days | > 45 days |

---

## Data source

BigFix Insights only. Four tables:

- `datasource_devices` — which servers exist and their status
- `device_dimensions` — server name and operating system
- `datasource_fixlets` — the patch catalogue and release dates
- `content_results` — which patch applies to which server, and when it was resolved

The report is **read-only**. It creates nothing in the database and needs only
SELECT permission.

---

## Parameters

You are prompted for these the first time you open the template. To change them
afterwards: **Home → Transform data → Manage Parameters**

| Parameter | Type | Example | What it does |
|---|---|---|---|
| `SqlServer` | Text | `11.11.11.11` | BigFix Insights SQL Server host |
| `SqlDatabase` | Text | `BFInsights` | Database name |
| `PatchSiteIds` | Text | `2,171` | Comma-separated site IDs that count as patch content. **No spaces.** |
| `SLADays` | Number | `45` | SLA window in days, measured from patch release date |
| `AnchorDate` | Text | `2026-07-31` | Last day of the most recently closed month. Format must be `yyyy-MM-dd` |
| `HistoryMonths` | Number | `13` | How many monthly periods to compute |
| `WeeklySnapshots` | Number | `13` | How many weekly periods to compute |

### Finding your PatchSiteIds

Run this against BigFix Insights and take the IDs of the genuine patch sites — they
will have fixlet counts in the hundreds or thousands:

```sql
SELECT s.id, s.name, COUNT(f.id) AS fixlets
FROM datasource_sites s
JOIN datasource_fixlets f
  ON f.datasource_site_id = s.id
 AND ISNULL(f.valid_to,'9999-12-31') > SYSUTCDATETIME()
 AND f.deleted = 0
 AND ISNULL(f.is_task,0) = 0
GROUP BY s.id, s.name
HAVING COUNT(f.id) > 0
ORDER BY fixlets DESC;
```

If `PatchSiteIds` is wrong, the report refreshes cleanly and shows **100%
compliance** — a wrong answer that looks like a right one. Check this first if the
numbers look too good.

---

## Setup

This repository holds a **`.pbit` template** — the report structure with no data in
it. Opening it builds your own copy against your database.

1. **Open the `.pbit`** in Power BI Desktop (double-click it)
2. **Fill in the parameters** — you are prompted immediately on open. See the table
   above for what each one needs
3. **Click Load.** Supply database credentials when prompted
4. **Approve the native database query** prompt when it appears
5. **File → Save As → Power BI file (.pbix)** — this is your working report

The template is not modified by opening it, so the same `.pbit` can be used by
several people, each producing their own `.pbix`.

Anyone opening it needs their own database access — the template carries the queries
and structure, not credentials.

To stop the approval prompt recurring on every parameter change:
**File → Options and settings → Options → Global → Security →** untick
*Require user approval for new native database queries*

---

## Monthly maintenance

**Update `AnchorDate`** to the last day of each newly closed month.

This does not happen automatically. If it is missed, the report keeps showing the
previous month's figures without any warning that they are stale.

---

## Notes on the numbers

- **Overall MTTP is event-weighted**, not an average of the Windows and \*Nix
  figures. Averaging those two gives a different, less accurate result.
- **MTTP excludes servers with no patch activity** in the period. The count excluded
  is shown on the card — without it, a growing backlog of untouched servers would
  make the average look better.
- **Scope includes agents that have stopped reporting.** A silent endpoint is a
  risk, not an absence, so it is counted rather than dropped.
- **Group figures overlap.** A server can belong to several BigFix groups, so group
  numbers will not sum to the estate total.

---

## Refresh cost

Each reporting period requires its own database query. With `HistoryMonths` and
`WeeklySnapshots` both at 13, that is 26 queries per refresh.

Keep these no higher than the largest trend window actually used — computing periods
that are never displayed costs refresh time for no benefit.
