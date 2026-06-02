import unittest

from app.core.linter import SlideLinter, _TextBoxStat


class SlideLinterDensityTests(unittest.TestCase):
    def test_reference_like_slide_exempts_expected_dense_bibliography_text(self) -> None:
        text = (
            "\u53c2\u8003\u6587\u732e "
            "[1] Johnson SR, Cordier JF, Lazor R. European Respiratory Journal 2010. "
            "[2] McCormack FX, Gupta N, Finlay GR. American Journal of Respiratory and Critical Care Medicine 2016. "
            "[3] Gupta N, Finlay GA, Kotloff RM. Chest 2017. "
            "[4] Taveira-DaSilva AM, Moss J. Clinics in Chest Medicine 2016."
        )
        self.assertTrue(SlideLinter._is_reference_like(text, 5))

    def test_numbered_year_lines_are_reference_like_even_without_reference_heading(self) -> None:
        text = (
            "1. Johnson SR, Cordier JF, Lazor R. European Respiratory Journal 2010. "
            "2. McCormack FX, Gupta N, Finlay GR. American Journal of Respiratory and Critical Care Medicine 2016. "
            "3. Gupta N, Finlay GA, Kotloff RM. Chest 2017. "
            "4. Taveira-DaSilva AM, Moss J. Clinics in Chest Medicine 2016."
        )
        self.assertTrue(SlideLinter._is_reference_like(text, 8))

    def test_journal_heavy_bibliography_is_reference_like_without_numbering(self) -> None:
        text = (
            "McCormack FX, Gupta N. Official ATS/JRS Clinical Practice Guidelines 2016. "
            "Johnson SR, Cordier JF. European Respiratory Society guidelines 2010. "
            "Taveira-DaSilva AM, Moss J. Clinical features in Chest Medicine 2015. "
            "Gupta N, Kotloff RM. Lymphangioleiomyomatosis diagnosis and management, Chest 2017."
        )
        self.assertTrue(SlideLinter._is_reference_like(text, 8))

    def test_ordinary_year_based_dense_slide_is_not_reference_like(self) -> None:
        text = (
            "\u968f\u8bbf\u7ba1\u7406 2010 \u5e74\u540e\u9700\u8981\u6309\u6708\u8bb0\u5f55\u75c7\u72b6\u3001"
            "\u8fd0\u52a8\u80fd\u529b\u3001\u5f71\u50cf\u53d8\u5316\u4e0e\u7528\u836f\u53cd\u5e94\uff0c"
            "\u5e76\u5728 2016 \u5e74\u6307\u5357\u57fa\u7840\u4e0a\u5efa\u7acb\u957f\u671f\u590d\u8bc4\u8282\u594f\u3002"
        )
        self.assertFalse(SlideLinter._is_reference_like(text, 4))

    def test_sparse_detail_boxes_should_warn(self) -> None:
        boxes = [
            _TextBoxStat(text="吞咽风险：筛查", align="l", cx=8500000, cy=820000),
            _TextBoxStat(text="运动能力：评估", align="l", cx=8500000, cy=820000),
            _TextBoxStat(text="认知状态：复评", align="l", cx=8500000, cy=820000),
            _TextBoxStat(text="并发症：监测", align="l", cx=8500000, cy=820000),
        ]
        issue = SlideLinter._sparse_content_issue("ppt/slides/slide10.xml", boxes)
        self.assertIsNotNone(issue)
        self.assertEqual(issue.level, "warn")

    def test_dense_detail_boxes_should_not_warn(self) -> None:
        boxes = [
            _TextBoxStat(text="吞咽风险：完成床旁筛查并记录误吸信号，按周复评并调整食物质地", align="l", cx=8500000, cy=820000),
            _TextBoxStat(text="运动能力：根据肌力与平衡结果制定训练频次，明确家庭执行动作与安全边界", align="l", cx=8500000, cy=820000),
            _TextBoxStat(text="认知状态：使用MoCA追踪注意与执行变化，出现下降时触发多学科会诊", align="l", cx=8500000, cy=820000),
            _TextBoxStat(text="并发症：重点监测癫痫与血栓风险，设置异常上报时限和处置路径", align="l", cx=8500000, cy=820000),
        ]
        issue = SlideLinter._sparse_content_issue("ppt/slides/slide10.xml", boxes)
        self.assertIsNone(issue)


if __name__ == "__main__":
    unittest.main()
