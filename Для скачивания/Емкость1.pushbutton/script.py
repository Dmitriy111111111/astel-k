# -*- coding: utf-8 -*-
# pyRevit / IronPython
# Пустотелая цилиндрическая емкость (DirectShape) + расчеты + класс элемента.
# Ввод в МЕТРАХ. Материал (rho,Sy), плотность жидкости, уровень заполнения,
# запись "Класс элемента", текст с расчетами рядом.

import math
from Autodesk.Revit.DB import (
    Transaction, XYZ, Arc, CurveLoop, GeometryCreationUtilities, DirectShape,
    BuiltInCategory, ElementId, GeometryObject, TextNote, TextNoteOptions,
    ElementTypeGroup, BuiltInParameter, TextNoteType, FilteredElementCollector
)
from System.Collections.Generic import List
from pyrevit import forms, revit

doc  = __revit__.ActiveUIDocument.Document
view = __revit__.ActiveUIDocument.ActiveView

# ---------- утилиты ----------
g = 9.81  # м/с^2

def m_to_ft(m):
    return float(m) / 0.3048

def ft_to_m(ft):
    return float(ft) * 0.3048

def pf(x, n=3):
    try:
        return ('%.' + str(n) + 'f') % float(x)
    except:
        return str(x)

def parse_float(s, default):
    try:
        return float((s or '').replace(',', '.'))
    except:
        return default

def ask_float(prompt, default_str, title=u"Ввод"):
    s = forms.ask_for_string(prompt=prompt, default=default_str, title=title)
    return parse_float(s, float(default_str))

def make_circle_loop(center, radius_ft, clockwise=False):
    loop = CurveLoop()
    step = -math.pi/2.0 if clockwise else math.pi/2.0
    angs = [0.0, 0.0 + step, 0.0 + 2*step, 0.0 + 3*step, 0.0 + 4*step]
    def pt(a):
        return XYZ(center.X + radius_ft*math.cos(a),
                   center.Y + radius_ft*math.sin(a),
                   center.Z)
    for i in range(4):
        a0, a1 = angs[i], angs[i+1]
        p0, p1 = pt(a0), pt(a1)
        pm = pt((a0 + a1)/2.0)
        loop.Append(Arc.Create(p0, p1, pm))
    return loop

def get_textnote_type_id(doc):
    # Берем тип текста по умолчанию, иначе любой доступный
    try:
        tid = doc.GetDefaultElementTypeId(ElementTypeGroup.TextNoteType)
        if tid and tid.IntegerValue > 0:
            return tid
    except:
        pass
    col = FilteredElementCollector(doc).OfClass(TextNoteType)
    for t in col:
        return t.Id
    return ElementId.InvalidElementId

# ---------- материал (rho, Sy) ----------
MATERIALS = {
    u"Сталь S235":       {"rho": 7850.0, "Sy": 235.0},
    u"Сталь S355":       {"rho": 7850.0, "Sy": 355.0},
    u"Сталь 09Г2С":      {"rho": 7850.0, "Sy": 345.0},
    u"Нерж 304":         {"rho": 8000.0, "Sy": 215.0},
    u"Нерж 316L":        {"rho": 8000.0, "Sy": 205.0},
    u"Алюминий 6061-T6": {"rho": 2700.0, "Sy": 240.0},
    u"Титан Grade 2":    {"rho": 4500.0, "Sy": 275.0},
}

mat_choice = forms.ask_for_one_item(sorted(MATERIALS.keys()),
                                    default=u"Сталь S235",
                                    prompt=u"Материал изготовления")
if mat_choice:
    rho_kg_m3 = MATERIALS[mat_choice]["rho"]
    Sy_MPa    = MATERIALS[mat_choice]["Sy"]
else:
    rho_kg_m3 = ask_float(u"Плотность материала, кг/м3:", "7850", title=u"Материал")
    Sy_MPa    = ask_float(u"Предел текучести, МПа:", "235", title=u"Материал")

gamma_mat_kN_m3 = rho_kg_m3 * g / 1000.0
allow_MPa = 0.6 * Sy_MPa  # упрощенное допускаемое

# ---------- геометрия ----------
D_out_m  = ask_float(u"Наружный диаметр, м:", "1.2", title=u"Геометрия")
t_wall_m = ask_float(u"Толщина стенки, м:", "0.05", title=u"Геометрия")
H_m      = ask_float(u"Высота, м:", "1.5", title=u"Геометрия")
t_bottom_m = ask_float(u"Толщина дна, м (0 - без дна):", "0.00", title=u"Геометрия")

# ---------- жидкость ----------
rho_fluid = ask_float(u"Плотность жидкости, кг/м3:", "1000", title=u"Жидкость")
gamma_fl_kN_m3 = rho_fluid * g / 1000.0

# ---------- класс элемента ----------
elem_class = forms.ask_for_string(prompt=u'Класс элемента (напр., "Емкость вертикальная")',
                                  default=u"Емкость", title=u"Класс элемента") or u"Емкость"

# ---------- точка вставки ----------
try:
    base_pt = revit.pick_point(u"Укажите точку: центр основания емкости (Esc - ввод XYZ)")
except Exception:
    xyz_str = forms.ask_for_string(
        prompt=u"Координаты центра основания X,Y,Z (м):",
        default="0,0,0", title=u"Координаты (м)"
    ) or "0,0,0"
    parts = [p.strip() for p in xyz_str.replace(";", ",").split(",")]
    while len(parts) < 3:
        parts.append("0")
    X_m = parse_float(parts[0], 0.0)
    Y_m = parse_float(parts[1], 0.0)
    Z_m = parse_float(parts[2], 0.0)
    base_pt = XYZ(m_to_ft(X_m), m_to_ft(Y_m), m_to_ft(Z_m))

# ---------- проверки ----------
if D_out_m <= 0 or t_wall_m <= 0 or H_m <= 0:
    forms.alert(u"Все размеры должны быть > 0.", title="pyRevit")
    raise SystemExit
R_out_m = D_out_m / 2.0
if t_wall_m >= R_out_m:
    forms.alert(u"Толщина стенки должна быть меньше радиуса (t < D/2).", title="pyRevit")
    raise SystemExit
if t_bottom_m < 0:
    t_bottom_m = 0.0

# ---------- геометрия заготовок ----------
R_in_m  = R_out_m - t_wall_m
R_out_ft, R_in_ft = m_to_ft(R_out_m), m_to_ft(R_in_m)
H_ft, t_bottom_ft = m_to_ft(H_m), m_to_ft(t_bottom_m)

outer = make_circle_loop(base_pt, R_out_ft, clockwise=False)
inner = make_circle_loop(base_pt, R_in_ft,  clockwise=True)
loops = List[CurveLoop]()
loops.Add(outer)
loops.Add(inner)

# ---------- расчеты ----------
H_inside_m = max(0.0, H_m - t_bottom_m)
fill_prompt = u"Уровень заполнения, м (<= {0}):".format(pf(H_inside_m))
fill_h_m = ask_float(fill_prompt, pf(H_inside_m), title=u"Жидкость")
if fill_h_m > H_inside_m: fill_h_m = H_inside_m
if fill_h_m < 0.0: fill_h_m = 0.0

V_inside_m3      = math.pi * (R_in_m**2) * H_inside_m               # полная вместимость
V_fluid_fill_m3  = math.pi * (R_in_m**2) * fill_h_m                 # текущий объем жидкости
V_shell_m3       = math.pi * (R_out_m**2 - R_in_m**2) * H_m         # стенка
V_bottom_m3      = math.pi * (R_in_m**2) * t_bottom_m if t_bottom_m > 0 else 0.0
V_metal_m3       = V_shell_m3 + V_bottom_m3

mass_metal_kg = rho_kg_m3 * V_metal_m3
mass_fluid_kg = rho_fluid * V_fluid_fill_m3
mass_total_kg = mass_metal_kg + mass_fluid_kg

W_metal_kN = gamma_mat_kN_m3 * V_metal_m3
W_fluid_kN = gamma_fl_kN_m3 * V_fluid_fill_m3
W_total_kN = W_metal_kN + W_fluid_kN

A_out_side_m2 = 2 * math.pi * R_out_m * H_m
A_in_side_m2  = 2 * math.pi * R_in_m  * H_inside_m
A_bottom_top_m2 = math.pi * (R_in_m**2) if t_bottom_m > 0 else 0.0
A_bottom_bot_m2 = math.pi * (R_in_m**2) if t_bottom_m > 0 else 0.0

# ---------- создание ----------
t = Transaction(doc, "Tank + Calc + Class")
t.Start()
try:
    solid_shell = GeometryCreationUtilities.CreateExtrusionGeometry(loops, XYZ.BasisZ, H_ft)
    solids = List[GeometryObject]()
    solids.Add(solid_shell)

    if t_bottom_m > 0:
        bottom_loop = make_circle_loop(base_pt, R_in_ft, clockwise=False)
        loops_bottom = List[CurveLoop]()
        loops_bottom.Add(bottom_loop)
        solid_bottom = GeometryCreationUtilities.CreateExtrusionGeometry(loops_bottom, XYZ.BasisZ, t_bottom_ft)
        solids.Add(solid_bottom)

    ds = DirectShape.CreateElement(doc, ElementId(BuiltInCategory.OST_GenericModel))
    ds.ApplicationId = "pyRevit"
    ds.ApplicationDataId = "hollow-cylinder-with-calc-and-class"
    ds.SetShape(solids)

    # Класс элемента
    pclass = ds.LookupParameter(u"Класс элемента")
    if pclass and (not pclass.IsReadOnly):
        try:
            pclass.Set(elem_class)
        except:
            pass
    else:
        pmark = ds.get_Parameter(BuiltInParameter.ALL_MODEL_MARK)
        if pmark and (not pmark.IsReadOnly):
            try:
                pmark.Set(elem_class)
            except:
                pass
        pcom = ds.get_Parameter(BuiltInParameter.ALL_MODEL_INSTANCE_COMMENTS)
        if pcom and (not pcom.IsReadOnly):
            try:
                base = pcom.AsString() or u""
                extra = u" | Класс: " + elem_class if elem_class else u""
                pcom.Set((base + extra) if base else (u"Класс: " + elem_class))
            except:
                pass

    # Комментарий кратко
    info_short = u"Емкость D={0:.3f} x H={1:.3f} м; t={2:.3f} м; Материал={3}; rho_m={4} кг/м3; rho_f={5} кг/м3".format(
        D_out_m, H_m, t_wall_m, mat_choice or u"-", int(rho_kg_m3), int(rho_fluid)
    )
    par = ds.get_Parameter(BuiltInParameter.ALL_MODEL_INSTANCE_COMMENTS)
    if par and not par.IsReadOnly:
        try:
            par.Set(info_short)
        except:
            pass

    # Текст-расчет рядом
    offset_m = max(0.2, R_out_m * 1.2)
    text_pt = XYZ(base_pt.X + m_to_ft(offset_m), base_pt.Y, base_pt.Z + m_to_ft(max(0.2, H_m*0.1)))

    tntype_id = get_textnote_type_id(doc)
    tnopt = TextNoteOptions(tntype_id)
    liters_cap  = V_inside_m3 * 1000.0
    liters_fill = V_fluid_fill_m3 * 1000.0

    text = (
        u"Емкость (пустотелая)\n"
        u"- Класс: {K}\n"
        u"- Материал: {MAT} (rho={RHOm} кг/м3, gamma={GAMm} кН/м3); Жидкость: rho={RHOf} кг/м3, gamma={GAMf} кН/м3\n"
        u"- Dн={D} м, H={H} м, tст={t} м, tдн={tb} м; Rвн={Ri} м\n"
        u"- Вместимость полная: {V_in} м3 ({Lcap} л); Заполнение: h={hf} м -> {Vf} м3 ({Lf} л)\n"
        u"- Объем металла: {Vmet} м3; Масса металла: {Mmet} кг; Вес металла: {Wmet} кН\n"
        u"- Масса жидкости: {Mfl} кг; Вес жидкости: {Wfl} кН\n"
        u"- Общий вес при заполнении h: {Wtot} кН (примерно {Ttot} т)\n"
        u"- Площади: наружн.бок.={Aos} м2; внутр.бок.={Ais} м2; дно верх/низ={At}/{Ab} м2"
    ).format(
        K=elem_class,
        MAT=mat_choice or u"-",
        RHOm=pf(rho_kg_m3,0), GAMm=pf(gamma_mat_kN_m3,2),
        RHOf=pf(rho_fluid,0),  GAMf=pf(gamma_fl_kN_m3,2),
        D=pf(D_out_m), H=pf(H_m), t=pf(t_wall_m), tb=pf(t_bottom_m), Ri=pf(R_in_m),
        V_in=pf(V_inside_m3), Lcap=pf(liters_cap,1),
        hf=pf(fill_h_m), Vf=pf(V_fluid_fill_m3), Lf=pf(liters_fill,1),
        Vmet=pf(V_metal_m3), Mmet=pf(mass_metal_kg,1), Wmet=pf(W_metal_kN,2),
        Mfl=pf(mass_fluid_kg,1), Wfl=pf(W_fluid_kN,2),
        Wtot=pf(W_total_kN,2), Ttot=pf(mass_total_kg/1000.0,2),
        Aos=pf(A_out_side_m2), Ais=pf(A_in_side_m2), At=pf(A_bottom_top_m2), Ab=pf(A_bottom_bot_m2)
    )

    try:
        TextNote.Create(doc, view.Id, text_pt, text, tnopt)
    except:
        pass

    t.Commit()
except Exception as e:
    t.RollBack()
    forms.alert(u"Ошибка: {0}".format(e), title="pyRevit")
