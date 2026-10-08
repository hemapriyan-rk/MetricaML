"""Builds the printable PDF summary of an experiment with ReportLab."""
from reportlab.graphics.charts.barcharts import HorizontalBarChart
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

COBALT = colors.HexColor("#2036C8")
INK = colors.HexColor("#18212B")
SLATE = colors.HexColor("#5D6A76")
RULE = colors.HexColor("#D5DAD3")
WASH = colors.HexColor("#EEF1EC")

_METRIC_LABELS = {
    "accuracy": "Accuracy", "precision": "Precision (weighted)", "recall": "Recall (weighted)",
    "f1": "F1 score (weighted)", "mae": "MAE", "mse": "MSE", "rmse": "RMSE", "r2": "R²",
}
_PERCENT = {"accuracy", "precision", "recall", "f1"}


def _fmt_metric(name: str, value: float) -> str:
    return f"{value * 100:.2f}%" if name in _PERCENT else f"{value:,.4f}"


def _table(rows, widths, header=False):
    t = Table(rows, colWidths=widths)
    style = [
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    if header:
        style += [("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("BACKGROUND", (0, 0), (-1, 0), WASH)]
    else:
        style += [("TEXTCOLOR", (0, 0), (0, -1), SLATE)]
    t.setStyle(TableStyle(style))
    return t


def build_report(path, results: dict, exp_row) -> None:
    base = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=base["Title"], fontName="Helvetica-Bold", fontSize=22, textColor=INK,
                        alignment=0, spaceAfter=2)
    sub = ParagraphStyle("sub", parent=base["Normal"], fontSize=10, textColor=SLATE, spaceAfter=10)
    h2 = ParagraphStyle("h2", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=12.5, textColor=COBALT,
                        spaceBefore=14, spaceAfter=6)
    small = ParagraphStyle("small", parent=base["Normal"], fontSize=8.5, textColor=SLATE, leading=11)

    ds, algo, host = results["dataset"], results["algorithm"], results["host"]
    story = [
        Paragraph(f"Experiment #{results['experiment_id']}", h1),
        Paragraph(f"{algo['label']} on {ds['filename']} &nbsp;|&nbsp; {results['problem_type'].title()} "
                  f"&nbsp;|&nbsp; target: {results['target']}", sub),
    ]

    story.append(Paragraph("Results", h2))
    rows = [[_METRIC_LABELS.get(k, k), _fmt_metric(k, v)] for k, v in results["metrics"].items()]
    base_info = results["baseline"]
    rows.append(["Baseline", f"{_fmt_metric(base_info['name'], base_info['value'])} ({base_info['description']})"])
    story.append(_table(rows, [60 * mm, 100 * mm]))
    story.append(Paragraph(f"Measured on {ds['rows_test']:,} held-out rows the model never saw during training.", small))

    importance = results["charts"]["importance"][:10]
    if importance:
        story.append(Paragraph("Most influential features", h2))
        d = Drawing(170 * mm, max(40 * mm, len(importance) * 7 * mm))
        chart = HorizontalBarChart()
        chart.x, chart.y = 38 * mm, 4 * mm
        chart.width, chart.height = 125 * mm, d.height - 8 * mm
        chart.data = [[max(i["importance"], 0) for i in reversed(importance)]]
        chart.categoryAxis.categoryNames = [i["feature"][:22] for i in reversed(importance)]
        chart.categoryAxis.labels.fontSize = 8
        chart.valueAxis.labels.fontSize = 7
        chart.valueAxis.valueMin = 0
        chart.bars[0].fillColor = COBALT
        chart.bars[0].strokeColor = None
        chart.barWidth = 6
        d.add(chart)
        story.append(d)
        story.append(Paragraph("Permutation importance: how much the score drops when a feature's values are shuffled.", small))

    if results["problem_type"] == "classification" and len(results["classes"]) <= 8:
        cm = results["charts"]["confusion"]
        story.append(Paragraph("Confusion matrix", h2))
        header = ["Actual \\ Predicted"] + [c[:12] for c in cm["labels"]]
        body = [[cm["labels"][i][:14]] + row for i, row in enumerate(cm["matrix"])]
        w = 150 * mm / (len(header))
        story.append(_table([header] + body, [w] * len(header), header=True))
    elif results["problem_type"] == "regression":
        res = results["charts"]["residuals"]
        story.append(Paragraph("Residuals", h2))
        story.append(_table([["Mean residual", f"{res['mean']:,.4f}"], ["Std. deviation", f"{res['std']:,.4f}"]],
                            [60 * mm, 100 * mm]))

    story.append(Paragraph("Configuration", h2))
    prep = results["preprocessing"]
    cfg_rows = [
        ["Algorithm", algo["label"]],
        *[[k.replace("_", " "), str(v)] for k, v in algo["params"].items()],
        ["Features", f"{len(results['features']['selected'])} selected ({results['features']['after_encoding']} after encoding)"],
        ["Missing values", f"{prep['missing'].replace('_', ' ')} (numeric), most frequent (categorical)"],
        ["Categorical encoding", prep["encoding"]],
        ["Scaling", prep["scaling"]],
        ["Train / test split", f"{round((1 - prep['test_size']) * 100)} / {round(prep['test_size'] * 100)}"],
        ["Random state", str(prep["random_state"])],
        ["Rows (train / test)", f"{ds['rows_train']:,} / {ds['rows_test']:,}"],
    ]
    story.append(_table(cfg_rows, [60 * mm, 100 * mm]))

    story.append(Paragraph("Where it ran", h2))
    where = host["provider"] + (f" {host['instance_type']}" if host.get("instance_type") else "")
    story.append(_table([
        ["Machine", where],
        ["Operating system", host["os"]],
        ["Python / scikit-learn", f"{host['python']} / {host['scikit_learn']}"],
        ["Training time", f"{results['training_seconds']:.2f} s"],
    ], [60 * mm, 100 * mm]))
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(f"Dataset SHA-256: {ds['sha256']}", small))

    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=18 * mm, bottomMargin=18 * mm, title=f"MetricaML experiment #{results['experiment_id']}",
                            author="MetricaML")
    doc.build(story)
