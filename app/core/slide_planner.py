from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional


@dataclass
class PlannedSlide:
    index: int
    title: str
    bullets: List[str]
    prototype_hint: str
    copy_pattern: str = "general"


class SlidePlanner:
    """Fallback planner used when AI output is unavailable or off-topic."""

    def build_reference_quality_plan(
        self,
        topic: str,
        audience: str = "",
        tone: str = "",
    ) -> Dict[str, object] | None:
        if not self._is_lam_topic(topic):
            return None
        return self._build_lam_teaching_plan(topic, audience=audience, tone=tone)

    def build_fallback_plan(
        self,
        topic: str,
        slide_count: int,
        audience: str = "",
        tone: str = "",
        conversation: Optional[List[Dict[str, str]]] = None,
        copy_patterns: Optional[List[Dict[str, object]]] = None,
    ) -> Dict[str, object]:
        safe_count = max(4, min(slide_count, 30))
        mode = self._topic_mode(topic)
        last_instruction = self._last_user_instruction(conversation)
        pattern_by_index = self._copy_pattern_by_index(copy_patterns)

        toc_items = self._toc_bullets(mode)[: max(1, min(5, safe_count - 3))]
        slides: List[Dict[str, object]] = [
            {
                "index": 1,
                "title": topic,
                "subtitle": f"{audience or '相关专业团队'} / {tone or '专业、清晰、可执行'}",
                "toc_items": [],
                "section_title": topic,
                "points": [],
                "summary_items": [],
                "bullets": [],
                "prototype_hint": "cover",
                "copy_pattern": pattern_by_index.get(1, "cover_toc"),
            },
            {
                "index": 2,
                "title": "目录",
                "subtitle": "",
                "toc_items": toc_items,
                "section_title": "目录",
                "points": [],
                "summary_items": [],
                "bullets": [],
                "prototype_hint": "toc",
                "copy_pattern": pattern_by_index.get(2, "cover_toc"),
            },
        ]

        content_budget = max(0, safe_count - 2 - len(toc_items) - 1)
        base_per_section = content_budget // max(1, len(toc_items))
        extra = content_budget % max(1, len(toc_items))
        for section_index, section in enumerate(toc_items):
            if len(slides) >= safe_count:
                break
            slides.append(
                {
                    "index": len(slides) + 1,
                    "title": section,
                    "subtitle": "",
                    "toc_items": [],
                    "section_title": section,
                    "points": [],
                    "summary_items": [],
                    "bullets": [],
                    "prototype_hint": "section",
                    "copy_pattern": "general",
                }
            )
            pages_for_section = base_per_section + (1 if section_index < extra else 0)
            for local_page in range(max(1 if len(toc_items) <= 2 else 0, pages_for_section)):
                if len(slides) >= safe_count - 1:
                    break
                pattern = pattern_by_index.get(len(slides) + 1, "general")
                bullets = self._section_bullets(topic, section, mode)
                bullets = self._apply_copy_pattern_to_bullets(topic, section, bullets, pattern)
                slides.append(
                    {
                        "index": len(slides) + 1,
                        "title": section if local_page == 0 else f"{section}要点",
                        "subtitle": "",
                        "toc_items": [],
                        "section_title": section,
                        "points": self._bullets_to_points(bullets),
                        "summary_items": [],
                        "bullets": [],
                        "prototype_hint": "content",
                        "copy_pattern": pattern,
                    }
                )

        if len(slides) < safe_count:
            slides.append(
                {
                    "index": len(slides) + 1,
                    "title": "总结",
                    "subtitle": "",
                    "toc_items": [],
                    "section_title": "总结",
                    "points": [],
                    "summary_items": ["阶段评估", "分层干预", "风险预警", "长期随访"],
                    "bullets": [],
                    "prototype_hint": "closing",
                    "copy_pattern": pattern_by_index.get(len(slides) + 1, "general"),
                }
            )

        if last_instruction and slides:
            for slide in reversed(slides):
                if slide.get("prototype_hint") == "content":
                    points = slide.get("points") if isinstance(slide.get("points"), list) else []
                    if points and isinstance(points[-1], dict):
                        points[-1]["body"] = f"{points[-1].get('body', '')}；用户补充要求：{last_instruction[:28]}"
                    break

        return {
            "deck_title": topic,
            "slides": slides[:safe_count],
            "source": "fallback",
        }

    @staticmethod
    def _is_lam_topic(topic: str) -> bool:
        normalized = (topic or "").lower()
        return "lam" in normalized or "肺淋巴管平滑肌瘤" in normalized

    def _build_lam_teaching_plan(self, topic: str, audience: str = "", tone: str = "") -> Dict[str, object]:
        slides: List[Dict[str, object]] = []

        def add(
            title: str,
            hint: str,
            *,
            section: str = "",
            toc_items: List[str] | None = None,
            points: List[Dict[str, str]] | None = None,
            bullets: List[str] | None = None,
            summary_items: List[str] | None = None,
            pattern: str = "general",
            subtitle: str = "",
            preferred_prototype_index: int = 0,
        ) -> None:
            slides.append(
                {
                    "index": len(slides) + 1,
                    "title": title,
                    "subtitle": subtitle,
                    "toc_items": toc_items or [],
                    "section_title": section or title,
                    "points": points or [],
                    "summary_items": summary_items or [],
                    "bullets": bullets or [],
                    "prototype_hint": hint,
                    "copy_pattern": pattern,
                    "preferred_prototype_index": preferred_prototype_index,
                }
            )

        def pts(*items: tuple[str, str]) -> List[Dict[str, str]]:
            return [{"label": label, "body": body} for label, body in items]

        add(
            "肺淋巴管平滑肌瘤病（LAM）\n的病因、临床表现与治疗",
            "cover",
            subtitle=audience or "PBL 病例汇报：20岁女性小杨",
            bullets=["肺淋巴管平滑肌瘤病（LAM）的病因、临床表现与治疗"],
            pattern="cover_toc",
        )
        add(
            "目录",
            "toc",
            toc_items=["病例线索与疾病定义", "发病机制与病因探讨", "典型临床表现剖析", "核心药物与多学科管理"],
            pattern="cover_toc",
        )
        add("病例线索与定义", "section", section="病例线索与疾病定义")
        add(
            "病例线索：小杨不是单纯气胸",
            "content",
            section="病例线索与疾病定义",
            pattern="dense_grid",
            points=pts(
                ("年轻女性", "20岁女性，育龄期人群，是LAM最典型的发病背景，需要主动追问月经、妊娠和激素暴露史。"),
                ("大量气胸", "右侧肺压缩约80%，起病急且程度重，提示囊性肺病导致胸膜下囊腔破裂的可能。"),
                ("乳糜胸", "乳白色胸水不是普通炎症渗出，提示淋巴系统受累和乳糜液回流障碍。"),
                ("囊性病变", "HRCT若提示双肺弥漫薄壁囊腔，同时合并肾血管平滑肌脂肪瘤和VEGF-D升高，应把这些线索合并成LAM证据链。"),
            ),
        )
        add(
            "LAM的定义",
            "content",
            section="病例线索与疾病定义",
            pattern="general",
            bullets=[
                "肺淋巴管平滑肌瘤病（LAM）是一种以异常平滑肌样细胞增殖为特征的罕见系统性疾病。",
                "病变主要累及肺、淋巴系统和肾脏，可造成弥漫性薄壁囊腔、气胸、乳糜胸和肾血管平滑肌脂肪瘤。",
                "LAM并非普通慢阻肺或单纯肺大疱，关键在于囊性肺破坏、淋巴侵犯和mTOR通路异常共同存在。",
                "诊断时应把患者性别年龄、HRCT形态、VEGF-D水平和肺外表现放在同一个疾病框架中理解。",
            ],
        )
        add(
            "为什么小杨的年龄和性别很典型？",
            "content",
            section="病例线索与疾病定义",
            pattern="label_detail",
            preferred_prototype_index=7,
            points=pts(
                ("人群特征", "LAM几乎均发生在女性，尤其集中于育龄期女性，病例中的20岁女性符合典型发病画像。"),
                ("散发性LAM", "多数患者没有明确遗传病史，可以气胸或活动后气促作为首发线索。"),
                ("TSC-LAM", "结节性硬化症相关LAM可合并皮肤、神经系统和肾脏表现，需要通过病史与体征筛查。"),
            ),
        )
        add("发病机制与病因探讨", "section", section="发病机制与病因探讨")
        add(
            "散发性与TSC相关LAM",
            "content",
            section="发病机制与病因探讨",
            pattern="label_detail",
            preferred_prototype_index=6,
            points=pts(
                ("散发性LAM", "多见于无TSC表现的女性，LAM细胞可携带TSC2体细胞突变，并呈现克隆性扩增特征；即使没有家族史，也不能排除LAM。"),
                ("TSC-LAM", "发生于结节性硬化症患者，常伴皮肤、神经系统和肾脏异常；两类LAM最终都指向TSC1/TSC2功能缺陷和mTOR异常激活。"),
            ),
        )
        add(
            "mTOR通路异常",
            "content",
            section="发病机制与病因探讨",
            pattern="general",
            preferred_prototype_index=14,
            points=pts(
                ("基因失活", "TSC1或TSC2失活使错构瘤蛋白复合体功能下降，细胞失去对生长信号的抑制。"),
                ("通路激活", "mTOR持续激活后，LAM细胞获得异常增殖、迁移和存活优势。"),
                ("组织侵犯", "异常细胞沿淋巴管和肺间质扩散，造成囊性破坏及乳糜相关并发症；西罗莫司抑制mTOR通路，正好对应这一核心机制。"),
            ),
        )
        add(
            "女性高发与雌激素",
            "content",
            section="发病机制与病因探讨",
            pattern="label_detail",
            preferred_prototype_index=10,
            points=pts(
                ("女性高发", "LAM几乎全部发生于女性，尤其集中在育龄期，这一流行病学特征提示雌激素可能参与疾病进展，但不能把LAM简单理解为单纯激素病。"),
                ("迁移侵袭", "雌激素可能增强LAM细胞迁移、侵袭和淋巴管播散能力，使囊性肺破坏、乳糜相关并发症和病情波动更容易被临床观察到。"),
                ("妊娠用药", "妊娠和外源性雌激素暴露需要专科评估，不能只按一般年轻女性气胸处理，必须结合肺功能、气胸史和乳糜并发症综合判断风险。"),
                ("患者教育", "患者教育要强调避免吸烟、慎用雌激素、记录症状变化，并在备孕或旅行前完成呼吸专科风险评估和随访计划调整。"),
            ),
        )
        add("典型临床表现剖析", "section", section="典型临床表现剖析")
        add(
            "临床表现之一：自发性气胸",
            "content",
            section="典型临床表现剖析",
            pattern="general",
            bullets=[
                "LAM患者肺内弥漫薄壁囊腔会削弱肺组织结构，胸膜下囊腔破裂后可出现自发性气胸。",
                "气胸可反复发生，且复发率明显高于普通原发性气胸，因此初次处理后就应考虑胸膜固定等复发预防策略。",
                "年轻女性出现反复气胸时，应主动追问活动后气促、乳糜胸、肾AML和TSC相关表现。",
                "影像检查不应只看有无气胸，还要寻找双肺弥漫、均匀分布的薄壁圆形囊腔。",
            ],
        )
        add(
            "临床表现之二：乳糜胸",
            "content",
            section="典型临床表现剖析",
            pattern="general",
            bullets=[
                "LAM细胞侵犯淋巴系统时，可造成淋巴回流受阻，乳糜液漏入胸腔后形成乳糜胸。",
                "乳糜胸表现为胸闷、气促和胸腔积液增多，胸水可呈乳白色，甘油三酯水平升高。",
                "处理时需结合低脂饮食、中链甘油三酯、胸腔引流、介入治疗和mTOR抑制剂综合决策。",
                "乳糜胸提示疾病不仅局限于肺实质，也反映LAM的系统性和淋巴侵犯特征。",
            ],
        )
        add(
            "LAM不只是肺病：还要关注肺外受累",
            "content",
            section="典型临床表现剖析",
            pattern="label_detail",
            points=pts(
                ("肾脏受累", "肾血管平滑肌脂肪瘤常与LAM并存，较大病灶存在出血风险，需要影像随访和介入评估。"),
                ("淋巴系统", "淋巴结、腹膜后或纵隔受累可形成淋巴管肌瘤，导致乳糜胸、乳糜腹水或腹部包块。"),
                ("肺部症状", "活动后气促、干咳、胸痛和反复气胸常与肺囊性破坏及通气受限相关。"),
                ("TSC线索", "皮肤、神经系统和肾脏表现可提示结节性硬化症相关LAM，需要系统筛查。"),
            ),
        )
        add("核心药物与多学科管理", "section", section="核心药物与多学科管理")
        add(
            "LAM治疗目标：控制进展，处理并发症",
            "content",
            section="核心药物与多学科管理",
            pattern="dense_grid",
            preferred_prototype_index=11,
            points=pts(
                ("稳定肺功能", "延缓FEV1和DLCO下降，减少活动后气促和低氧相关限制。"),
                ("处理并发症", "针对气胸、乳糜胸和肾AML建立早期识别与处理路径。"),
                ("长期管理", "通过定期肺功能、影像和药物安全监测，动态调整治疗强度。"),
                ("生活指导", "避免吸烟和雌激素暴露，妊娠前评估风险并制定专科随访计划。"),
            ),
        )
        add(
            "核心药物：西罗莫司抑制mTOR通路",
            "content",
            section="核心药物与多学科管理",
            pattern="label_detail",
            preferred_prototype_index=10,
            points=pts(
                ("作用机制", "西罗莫司作为mTOR抑制剂，可抑制异常激活的细胞生长信号，延缓肺功能下降。"),
                ("适用情境", "适用于肺功能下降、乳糜并发症、较大或进展性肾AML等需要系统治疗的患者。"),
                ("疗效观察", "治疗期间重点观察FEV1、DLCO、乳糜积液、肾AML体积和运动耐量变化。"),
                ("安全监测", "需监测血药浓度、血脂、口腔溃疡、感染风险和肝肾功能。"),
            ),
        )
        add(
            "小杨第一幕：先救急",
            "content",
            section="核心药物与多学科管理",
            pattern="process",
            points=pts(
                ("紧急处理", "大量气胸伴肺压缩约80%时，应立即吸氧、监测生命体征并行胸腔闭式引流。"),
                ("预防复发", "LAM相关气胸复发率高，初次气胸后就应尽早讨论胸膜固定术等策略。"),
                ("同步评估", "处理急症同时完善HRCT、VEGF-D、肺功能和肾脏影像评估。"),
                ("患者教育", "告知避免剧烈运动和气压骤变环境，出现胸痛气促时及时就医。"),
            ),
        )
        add(
            "小杨第二幕：乳糜胸的处理",
            "content",
            section="核心药物与多学科管理",
            pattern="dense_grid",
            points=pts(
                ("饮食控制", "采用低脂饮食和中链甘油三酯，减少乳糜液生成。"),
                ("引流药物", "根据积液量决定胸腔引流，并评估西罗莫司治疗指征。"),
                ("营养支持", "长期乳糜漏需监测白蛋白、电解质和免疫状态。"),
                ("介入选择", "保守治疗失败时可考虑胸导管介入、胸膜固定或外科方案。"),
            ),
        )
        add(
            "LAM长期随访与MDT管理",
            "content",
            section="核心药物与多学科管理",
            pattern="dense_grid",
            preferred_prototype_index=14,
            points=pts(
                ("肺功能监测", "定期复查FEV1、DLCO和运动耐量，识别疾病进展。"),
                ("影像随访", "HRCT根据症状和肺功能变化安排，避免无必要的过度检查。"),
                ("并发筛查", "随访需同步评估气胸复发风险、乳糜积液变化和肾AML大小，不把LAM当成单纯肺病管理，并把结果用于复诊频率和治疗升级判断。"),
                ("长期协作", "西罗莫司安全监测、妊娠风险评估、心理支持和呼吸-胸外-肾脏-康复协作，应写入长期管理计划，并明确复诊责任人与异常预警阈值。"),
            ),
        )
        add(
            "小杨的日常注意事项：患者教育",
            "content",
            section="核心药物与多学科管理",
            pattern="label_detail",
            preferred_prototype_index=10,
            points=pts(
                ("避免加重因素", "避免吸烟和雌激素相关用药，飞行、潜水或高海拔活动前需咨询医生。"),
                ("呼吸保护", "出现突发胸痛、气促加重或咯血时，应尽快就医排查气胸和感染。"),
                ("规律随访", "按计划复查肺功能、肾脏影像和药物安全指标，不因症状稳定而中断管理。"),
                ("生活方式", "保持适量运动和肺康复训练，避免过度疲劳，同时建立疾病记录。"),
            ),
        )
        add(
            "总结：LAM的全程管理",
            "closing",
            section="总结",
            pattern="label_detail",
            points=pts(
                ("早期精准诊断", "结合育龄期女性典型表现、HRCT弥漫囊状影、乳糜胸和VEGF-D升高，可更早把病例从普通气胸转向LAM诊断。"),
                ("靶向治疗主线", "TSC1/TSC2异常与mTOR通路激活解释了病因机制，也解释了西罗莫司为何是进展性LAM的核心疾病修饰治疗。"),
                ("全程综合管理", "急性期处理气胸和乳糜胸，长期随访肺功能、肾AML、药物安全、妊娠风险和生活质量，才接近真实临床管理。"),
            ),
        )
        add(
            "参考文献页",
            "reference",
            section="总结",
            pattern="general",
            bullets=[
                "葛均波，徐永健，王辰. 内科学[M]. 9版. 北京: 人民卫生出版社, 2018.",
                "中华医学会呼吸病学分会间质性肺疾病学组，淋巴管肌瘤病共识专家组，等. 西罗莫司治疗淋巴管肌瘤病专家共识（2018）[J]. 中华结核和呼吸杂志, 2019, 42(2):92-97.",
                "McCormack FX, Gupta N, Finlay GR, et al. Official ATS/JRS Clinical Practice Guidelines: Lymphangioleiomyomatosis diagnosis and management. Am J Respir Crit Care Med, 2016.",
                "Johnson SR, Cordier JF, Lazor R, et al. European Respiratory Society guidelines for lymphangioleiomyomatosis. Eur Respir J, 2010.",
                "Taveira-DaSilva AM, Moss J. Clinical features, epidemiology, and therapy of lymphangioleiomyomatosis. Clin Epidemiol, 2015.",
                "Gupta N, Finlay GA, Kotloff RM, et al. Lymphangioleiomyomatosis diagnosis and management: high-resolution CT, VEGF-D, and lung function follow-up.",
                "LAM Foundation clinical resources and patient management materials: pneumothorax, chylous effusion, sirolimus, pregnancy counseling and long-term follow-up.",
                "赵杰，李杰，刘鑫，等. 肺淋巴管肌瘤病一例报告及文献复习[J]. 中华胸部外科电子杂志, 2018.",
                "补充检索建议：结合最新指南、罕见病登记研究和患者教育材料更新随访频率、妊娠咨询与肺康复建议。",
                "相关呼吸病学、胸外科、罕见病和多学科管理综述文献。",
            ],
        )

        self._densify_lam_teaching_plan(slides)
        return {"deck_title": topic, "slides": slides, "source": "reference_quality_lam"}

    @staticmethod
    def _densify_lam_teaching_plan(slides: List[Dict[str, object]]) -> None:
        slide_notes = {
            "年龄和性别": "这一页应把病例特征和诊断思路连起来说明：年轻女性、气胸、乳糜胸和肾AML不是孤立线索，而是共同指向LAM的证据链。",
            "mTOR通路": "讲解时要强调该机制不是抽象分子背景，而是连接遗传异常、组织破坏和靶向治疗选择的主线。",
            "乳糜胸": "还要说明乳糜胸会导致营养、免疫和生活质量问题，因此治疗目标不只是把胸水引出来。",
            "治疗目标": "治疗策略应按急性并发症、慢性进展控制、肺外受累和生活质量四条线同步展开，避免只讲药物。",
            "西罗莫司": "这一页需要同时说明适应证、疗效观察和安全监测，否则听众只知道药名，不知道何时用、怎样评估疗效。",
            "第一幕": "结合病例第一幕，应突出先救急、再查因、再防复发的处理顺序，体现LAM气胸不同于普通气胸。",
            "第二幕": "结合病例第二幕，应把低脂饮食、引流、药物和介入治疗放到同一个阶梯化路径里说明。",
        }
        label_notes = {
            "人群特征": "这能帮助学生在接触年轻女性反复气胸时，主动把罕见囊性肺病纳入鉴别诊断。",
            "散发性LAM": "即使没有家族史，也不能因此排除LAM，关键要结合HRCT囊腔形态和肺外表现。",
            "TSC-LAM": "识别TSC相关线索有助于追加皮肤、神经系统、肾脏和遗传咨询层面的评估。",
            "基因失活": "这一步解释了为什么疾病具有肿瘤样增殖特征，但临床表现又常以呼吸和淋巴并发症为主。",
            "通路激活": "持续激活的mTOR信号会推动细胞增殖和代谢改变，使病变具备长期进展基础。",
            "组织侵犯": "组织侵犯最终落实为肺囊腔扩大、气胸复发和乳糜相关并发症，是影像与症状的共同来源。",
            "治疗靶点": "因此靶向治疗不是经验用药，而是围绕发病机制建立的疾病修饰治疗。",
            "紧急处理": "大量气胸时首先保证通气和循环稳定，不能为了完善诊断而延误闭式引流。",
            "预防复发": "LAM相关气胸复发率高，胸膜固定等预防措施应比普通气胸更早进入讨论。",
            "同步评估": "急症稳定后应尽快补齐HRCT、VEGF-D、肺功能和肾脏影像，完成从事件到疾病的转换。",
            "饮食控制": "饮食控制是减少乳糜生成的基础措施，但需要营养评估配合，不能简单长期严格限脂。",
            "引流药物": "引流解决当前积液，西罗莫司等系统治疗才可能减少反复乳糜漏的疾病基础。",
            "营养支持": "长期乳糜漏会造成白蛋白下降、淋巴细胞丢失和体力下降，需要动态监测。",
            "并发筛查": "筛查结果要和复诊频率、影像复查时点及治疗升级条件直接挂钩。",
            "长期协作": "同时明确复诊责任人、异常预警阈值和需要提前就医的触发条件。",
            "避免加重因素": "这些建议要写成患者能执行的规则，而不是停留在泛泛的健康宣教。",
            "呼吸保护": "突发胸痛和气促加重在LAM患者中优先排查气胸，不能只按普通呼吸道感染处理。",
            "规律随访": "随访的价值在于提前发现肺功能下降和肾AML变化，帮助决定是否启动或调整治疗。",
            "生活方式": "肺康复和日常活动应强调量力而行、循序渐进，目标是维持耐量而不是完全卧床休息。",
        }
        for slide in slides:
            if slide.get("prototype_hint") != "content":
                continue
            title = str(slide.get("title") or "")
            if "年龄和性别" in title or "日常注意" in title or "第二幕" in title:
                continue
            note = next((value for key, value in slide_notes.items() if key in title), "")
            points = slide.get("points") if isinstance(slide.get("points"), list) else []
            if points:
                for point in points:
                    if not isinstance(point, dict):
                        continue
                    label = str(point.get("label") or "")
                    extra = label_notes.get(label, "")
                    if extra and extra not in str(point.get("body") or ""):
                        point["body"] = f"{point.get('body')}{extra}"
                if note:
                    points[-1]["body"] = f"{points[-1].get('body')}{note}"
            elif note:
                bullets = slide.get("bullets") if isinstance(slide.get("bullets"), list) else []
                if note not in bullets:
                    bullets.append(note)
                slide["bullets"] = bullets

        for slide in slides:
            if slide.get("prototype_hint") != "content":
                continue
            if "参考" in str(slide.get("title") or ""):
                continue
            section = str(slide.get("section_title") or "")
            title = str(slide.get("title") or "")
            used_additions = SlidePlanner._long_sentences_in_slide(slide)
            points = slide.get("points") if isinstance(slide.get("points"), list) else []
            if points:
                for point in points:
                    if not isinstance(point, dict):
                        continue
                    label = str(point.get("label") or "")
                    body = str(point.get("body") or "")
                    point["body"] = SlidePlanner._expand_lam_teaching_body(title, section, label, body, used_additions)
                continue
            bullets = slide.get("bullets") if isinstance(slide.get("bullets"), list) else []
            enriched_bullets: List[str] = []
            for bullet in bullets:
                text = str(bullet or "")
                if "：" in text:
                    label, body = text.split("：", 1)
                    body = SlidePlanner._expand_lam_teaching_body(title, section, label, body, used_additions)
                    enriched_bullets.append(f"{label}：{body}")
                else:
                    enriched_bullets.append(SlidePlanner._expand_lam_teaching_body(title, section, "", text, used_additions))
            slide["bullets"] = enriched_bullets

        SlidePlanner._rebalance_lam_content_density(slides)

    @staticmethod
    def _rebalance_lam_content_density(slides: List[Dict[str, object]]) -> None:
        for slide in slides:
            if slide.get("prototype_hint") != "content":
                continue
            if "参考" in str(slide.get("title") or ""):
                continue

            points = slide.get("points") if isinstance(slide.get("points"), list) else []
            bullets = slide.get("bullets") if isinstance(slide.get("bullets"), list) else []
            target_units = 235
            if len(points) >= 4 or len(bullets) >= 4:
                body_floor = 34
                body_ceiling = 42
            elif len(points) == 3 or len(bullets) == 3:
                body_floor = 50
                body_ceiling = 66
            else:
                body_floor = 60
                body_ceiling = 80

            if points:
                for point in points:
                    if isinstance(point, dict):
                        point["body"] = SlidePlanner._fit_lam_body_text(
                            str(point.get("body") or ""),
                            floor=body_floor,
                            ceiling=body_ceiling,
                        )
                while SlidePlanner._slide_text_units(slide) > target_units:
                    longest = max(
                        (point for point in points if isinstance(point, dict)),
                        key=lambda item: len(SlidePlanner._clean_units(str(item.get("body") or ""))),
                    )
                    body = str(longest.get("body") or "")
                    shortened = SlidePlanner._fit_lam_body_text(body, floor=body_floor, ceiling=max(body_floor, body_ceiling - 8))
                    if shortened == body:
                        break
                    longest["body"] = shortened
                continue

            if bullets:
                rebalanced: List[str] = []
                for bullet in bullets:
                    text = str(bullet or "")
                    if "：" in text:
                        label, body = text.split("：", 1)
                        body = SlidePlanner._fit_lam_body_text(body, floor=body_floor, ceiling=body_ceiling)
                        rebalanced.append(f"{label}：{body}")
                    else:
                        rebalanced.append(SlidePlanner._fit_lam_body_text(text, floor=body_floor, ceiling=body_ceiling))
                slide["bullets"] = rebalanced

    @staticmethod
    def _fit_lam_body_text(text: str, *, floor: int, ceiling: int) -> str:
        text = str(text or "").strip()
        if len(SlidePlanner._clean_units(text)) <= ceiling:
            return text
        sentences = [item for item in re.split(r"(?<=[。！？!?])", text) if item.strip()]
        kept: List[str] = []
        for sentence in sentences:
            candidate = "".join(kept) + sentence.strip()
            candidate_units = len(SlidePlanner._clean_units(candidate))
            current_units = len(SlidePlanner._clean_units("".join(kept)))
            if kept and current_units >= floor and candidate_units > ceiling:
                break
            kept.append(sentence.strip())
            if candidate_units >= floor:
                break
        shortened = "".join(kept).strip()
        if shortened:
            return shortened
        clipped = SlidePlanner._clean_units(text)[:ceiling]
        return clipped.rstrip("，、；：") + "。"

    @staticmethod
    def _slide_text_units(slide: Dict[str, object]) -> int:
        chunks = [
            str(slide.get("title") or ""),
            str(slide.get("subtitle") or ""),
            *[str(item or "") for item in slide.get("toc_items", []) if isinstance(slide.get("toc_items"), list)],
            *[str(item or "") for item in slide.get("bullets", []) if isinstance(slide.get("bullets"), list)],
            *[str(item or "") for item in slide.get("summary_items", []) if isinstance(slide.get("summary_items"), list)],
        ]
        points = slide.get("points") if isinstance(slide.get("points"), list) else []
        for point in points:
            if isinstance(point, dict):
                chunks.append(str(point.get("label") or ""))
                chunks.append(str(point.get("body") or ""))
        return sum(len(SlidePlanner._clean_units(chunk)) for chunk in chunks)

    @staticmethod
    def _clean_units(text: str) -> str:
        return re.sub(r"\s+", "", str(text or ""))

    @staticmethod
    def _expand_lam_teaching_body(
        title: str,
        section: str,
        label: str,
        body: str,
        used_additions: set[str] | None = None,
    ) -> str:
        body = str(body or "").strip()
        if len(body) >= 58:
            return body

        context = f"{title}{section}{label}"
        selector = f"{context}{body}"
        if any(token in context for token in ("气胸", "胸腔", "急")):
            additions = [
                "这类气胸复发概率高，讲解时要把首次处理和后续预防放在同一条线上。",
                "需要提示学生先稳定通气，再回到囊性肺病这个病因线索上追问和检查。",
                "它不是一次孤立胸痛事件，而是LAM结构性肺破坏暴露出来的急性窗口。",
                "处理后仍要讨论胸膜固定和影像复查，否则很容易只完成急救而漏掉病因。",
            ]
        elif any(token in context for token in ("乳糜", "淋巴")):
            additions = [
                "乳糜漏会牵连营养、免疫和体力状态，因此管理目标不能只停在引流。",
                "这条线索把疾病从肺实质扩展到淋巴系统，有助于解释为什么需要全身管理。",
                "需要把胸水性质、饮食干预、药物治疗和介入选择串成阶梯化路径。",
                "反复积液会影响活动耐量和生活质量，随访时要把症状和实验室指标一起看。",
            ]
        elif any(token in context for token in ("mTOR", "TSC", "基因", "通路", "机制")):
            additions = [
                "这能把基因异常、细胞增殖和囊性肺破坏连接到同一条病因链上。",
                "讲机制时要落回临床：它解释了为什么西罗莫司能成为疾病修饰治疗。",
                "机制不是孤立背景知识，而是判断肺外受累和长期治疗策略的依据。",
                "这部分适合用证据链讲法，让听众看到从分子异常到症状表现的转换。",
            ]
        elif any(token in context for token in ("西罗莫司", "治疗", "药物", "管理")):
            additions = [
                "治疗决策要同时回答何时启动、看什么疗效指标、如何处理不良反应。",
                "这一页应避免只列药名，要把急性并发症和长期控制目标分开说明。",
                "管理路径需要体现多学科协作，尤其是呼吸、胸外、肾脏和康复随访。",
                "把药物疗效和肺功能、乳糜积液、肾AML变化相连，听众才知道怎样复评。",
            ]
        elif any(token in context for token in ("随访", "日常", "教育", "长期")):
            additions = [
                "建议要落到患者能执行的场景，例如飞行、妊娠、突发胸痛和复查节点。",
                "长期随访的价值在于提前识别进展，而不是症状稳定后简单停止管理。",
                "患者教育应给出风险信号和行动路径，让本人知道何时需要尽快就医。",
                "康复目标是维持活动耐量和生活质量，应和肺功能变化一起动态调整。",
            ]
        elif any(token in context for token in ("诊断", "定义", "表现", "受累", "类型")):
            additions = [
                "这会直接改变鉴别诊断方向，使年轻女性气胸不再被简单归为肺大疱。",
                "讲清这点后，HRCT、VEGF-D、肾脏影像和TSC筛查才有明确顺序。",
                "它提示LAM是多系统疾病，不能只按普通肺部症状做单点解释。",
                "这类信息适合放进病例推理，让听众理解每条证据为什么有诊断价值。",
            ]
        else:
            additions = [
                "补足判断依据和临床意义后，这一页才能直接服务于病例讨论。",
                "建议把下一步处理说清楚，让听众知道这个知识点如何落地。",
                "这部分要避免概念堆叠，重点放在为什么重要以及下一步怎么做。",
                "用病例中的证据带出结论，比单独罗列概念更接近真实汇报节奏。",
            ]

        start = sum((idx + 1) * ord(ch) for idx, ch in enumerate(selector)) % len(additions)
        used = used_additions if used_additions is not None else set()
        for offset in range(len(additions)):
            addition = additions[(start + offset) % len(additions)]
            if addition in body:
                continue
            if addition in used:
                continue
            if addition not in body:
                body = f"{body}{addition}"
                used.add(addition)
            if len(body) >= 62:
                break
        return body

    @staticmethod
    def _long_sentences_in_slide(slide: Dict[str, object]) -> set[str]:
        chunks: List[str] = []
        bullets = slide.get("bullets") if isinstance(slide.get("bullets"), list) else []
        chunks.extend(str(item or "") for item in bullets)
        points = slide.get("points") if isinstance(slide.get("points"), list) else []
        for point in points:
            if isinstance(point, dict):
                chunks.append(str(point.get("body") or ""))
        return {
            item.strip()
            for chunk in chunks
            for item in re.split(r"[。！？!?]", chunk)
            if len(item.strip()) >= 18
        }

    @staticmethod
    def _bullets_to_points(bullets: List[str]) -> List[Dict[str, str]]:
        points: List[Dict[str, str]] = []
        for bullet in bullets[:6]:
            if "：" in bullet:
                label, body = bullet.split("：", 1)
            elif ":" in bullet:
                label, body = bullet.split(":", 1)
            else:
                label, body = bullet[:8], bullet
            label = label.strip()[:12]
            body = body.strip()
            if label and body:
                points.append({"label": label, "body": body})
        return points

    @staticmethod
    def _copy_pattern_by_index(copy_patterns: Optional[List[Dict[str, object]]]) -> Dict[int, str]:
        out: Dict[int, str] = {}
        for item in copy_patterns or []:
            try:
                idx = int(item.get("index", 0))
            except (TypeError, ValueError):
                continue
            pattern = str(item.get("copy_pattern", "")).strip()
            if idx > 0 and pattern:
                out[idx] = pattern
        return out

    @staticmethod
    def _apply_copy_pattern_to_bullets(topic: str, section: str, bullets: List[str], pattern: str) -> List[str]:
        pattern_key = (pattern or "general").strip().lower()
        if pattern_key == "dense_grid":
            return [f"{b.split('：', 1)[0]}：保留关键动作与复评指标" for b in bullets[:6]]
        if pattern_key == "process":
            return [f"{section}阶段：围绕{topic}完成{b[:18]}并记录判断标准" for b in bullets[:4]]
        if pattern_key == "label_detail":
            return [f"{b.split('：', 1)[0]}：围绕{topic}明确执行动作、风险控制与复评指标" for b in bullets[:4]]
        return bullets

    @staticmethod
    def _last_user_instruction(conversation: Optional[List[Dict[str, str]]]) -> str:
        if not conversation:
            return ""
        for item in reversed(conversation):
            if str(item.get("role", "")).lower() == "user":
                text = str(item.get("content", "")).strip()
                if text:
                    return text
        return ""

    @staticmethod
    def _topic_mode(topic: str) -> str:
        if any(k in topic for k in ("脑卒中", "卒中", "脑梗", "脑出血")):
            return "stroke"
        if "胶质瘤" in topic:
            return "glioma"
        if any(k in topic for k in ("康复", "神经", "肿瘤", "临床", "随访")):
            return "medical"
        return "general"

    @staticmethod
    def _toc_bullets(mode: str) -> List[str]:
        if mode == "stroke":
            return [
                "出院评估与分层",
                "30-60-90天随访路径",
                "运动/吞咽/认知康复",
                "质量指标与风险预案",
            ]
        if mode == "glioma":
            return [
                "围手术期与放化疗期评估",
                "多维功能康复干预",
                "家庭管理与随访闭环",
                "结局指标与质量控制",
            ]
        if mode == "medical":
            return [
                "人群分层与阶段目标",
                "核心干预路径",
                "随访与风险管理",
                "指标与持续改进",
            ]
        return [
            "现状与目标",
            "关键策略",
            "执行节奏",
            "评估与优化",
        ]

    @staticmethod
    def _section_titles(mode: str) -> List[str]:
        if mode == "stroke":
            return [
                "出院评估与分层标准",
                "90天管理时间轴",
                "运动功能康复路径",
                "吞咽与营养管理",
                "语言与认知训练",
                "二级预防与用药依从",
                "家庭照护与远程随访",
                "结局指标与质量复盘",
            ]
        if mode == "glioma":
            return [
                "适应证与介入时机",
                "围手术期康复重点",
                "放化疗期支持方案",
                "运动与平衡训练",
                "认知语言与吞咽干预",
                "症状管理与风险预警",
                "家庭康复与长期随访",
                "量化指标与MDT协同",
            ]
        if mode == "medical":
            return [
                "目标人群与分层",
                "阶段任务与节奏",
                "核心干预策略",
                "依从性与风险管理",
                "随访机制与协同",
                "指标与复盘优化",
            ]
        return [
            "背景与目标",
            "关键问题",
            "方案路径",
            "执行计划",
            "风险与应对",
            "评估指标",
        ]

    def _section_bullets(self, topic: str, section: str, mode: str) -> List[str]:
        if mode == "stroke":
            section_map: Dict[str, List[str]] = {
                "出院评估与分层标准": [
                    "以 NIHSS、mRS、Barthel 建立出院基线",
                    "按运动/吞咽/认知风险进行三级分层",
                    "明确高风险患者48小时内首次随访",
                    "形成个体化90天康复处方",
                ],
                "90天管理时间轴": [
                    "第7天：电话随访症状与用药",
                    "第30天：门诊复评功能与并发症",
                    "第60天：强化训练与家庭执行督导",
                    "第90天：结局评估与下一阶段计划",
                ],
                "运动功能康复路径": [
                    "以 Fugl-Meyer 分项设定训练强度",
                    "步态、平衡、转移能力分模块推进",
                    "每周记录训练频次与达标率",
                    "异常疲劳或疼痛触发强度回调",
                ],
                "吞咽与营养管理": [
                    "出院前完成吞咽筛查与风险分级",
                    "制定食物质地与进食姿势方案",
                    "每2周复核体重、白蛋白、误吸风险",
                    "高风险者联动营养师与言语治疗师",
                ],
                "语言与认知训练": [
                    "评估失语类型与认知缺损维度",
                    "每日短时高频训练提升依从性",
                    "家庭任务卡配合复述与命名训练",
                    "30/60/90天复评并调整目标",
                ],
                "二级预防与用药依从": [
                    "抗栓、降压、降脂方案标准化核对",
                    "建立用药清单与漏服追踪机制",
                    "每次随访记录血压和不良反应",
                    "高复发风险患者纳入重点管理",
                ],
                "家庭照护与远程随访": [
                    "培训照护者转移与防跌倒技巧",
                    "远程打卡采集训练与症状数据",
                    "异常指标24小时内触发回访",
                    "保持医护-家庭双向沟通闭环",
                ],
                "结局指标与质量复盘": [
                    "核心指标：mRS改善率、Barthel提升值",
                    "过程指标：随访完成率、训练执行率",
                    "安全指标：再入院率、误吸事件率",
                    "按月复盘并迭代路径标准",
                ],
            }
            return section_map.get(
                section,
                [
                    f"围绕{topic}定义{section}目标",
                    "明确关键动作与责任分工",
                    "设置时间节点与质控标准",
                    "形成闭环随访与复盘机制",
                ],
            )

        if mode == "glioma":
            return [
                f"围绕{section}制定胶质瘤康复目标",
                "覆盖运动、认知、吞咽与心理维度",
                "按阶段设置随访频次与触发条件",
                "用量化指标评估干预效果",
            ]

        if mode == "medical":
            return [
                f"结合{topic}明确{section}重点",
                "定义流程节点与执行标准",
                "设置风险预警与升级规则",
                "使用指标追踪并持续优化",
            ]

        return [
            f"围绕{topic}阐明{section}",
            "明确可执行动作与负责人",
            "给出时间节奏与里程碑",
            "定义评估标准与复盘机制",
        ]
