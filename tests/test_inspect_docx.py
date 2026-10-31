import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'inspect_docx.py'
spec = importlib.util.spec_from_file_location('inspect_docx', SCRIPT)
inspector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inspector)
W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
M = 'http://schemas.openxmlformats.org/officeDocument/2006/math'
SAMPLE = f'''<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="{W}" xmlns:m="{M}"><w:body>
<w:tbl><w:tr><w:tc><w:tcPr><w:gridSpan w:val="2"/></w:tcPr>
<w:p><w:r><w:t>指导老师意见</w:t></w:r></w:p>
<w:tbl><w:tr><w:tc><w:p><w:r><w:t>内部</w:t></w:r></w:p></w:tc></w:tr></w:tbl>
<w:p><m:oMath><m:r><m:t>x</m:t></m:r></m:oMath></w:p>
</w:tc></w:tr></w:tbl></w:body></w:document>'''.encode('utf-8')


def fixture(path, document=SAMPLE, extra=()):
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('[Content_Types].xml', b'<Types/>')
        z.writestr('_rels/.rels', b'<Relationships/>')
        z.writestr('word/document.xml', document)
        for name, blob in extra:
            z.writestr(name, blob)


class TestInspector(unittest.TestCase):
    def test_nested_merge_approval_math_and_read_only(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / '测试.docx'; fixture(p, extra=[('word/comments.xml', b'<comments/>')])
            before = p.read_bytes(); r = inspector.inspect(p)
            self.assertEqual(before, p.read_bytes())
            self.assertEqual(r['status'], 'partial_structure_inspected')
            self.assertEqual(r['counts']['top_level_tables'], 1)
            self.assertEqual(r['counts']['all_tables_in_body'], 2)
            self.assertEqual(r['counts']['math_objects'], 1)
            self.assertEqual(r['counts']['physical_cells_listed'], 2)
            self.assertTrue(r['cells'][0]['merged_marker'])
            self.assertTrue(r['cells'][0]['possible_approval_text'])
            self.assertEqual(r['cells'][1]['nesting_depth'], 1)
            self.assertNotIn('direct_text_preview', r['cells'][0])
            self.assertTrue(r['package_features']['comments_part'])
            self.assertTrue(r['read_only'])
            self.assertIn('指导老师意见', inspector.inspect(p, True)['cells'][0]['direct_text_preview'])

    def test_old_format_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'form.doc'; p.write_bytes(b'not docx')
            with self.assertRaisesRegex(ValueError, '仅支持'):
                inspector.inspect(p)

    def test_bad_zip_and_missing_part_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'bad.docx'; p.write_bytes(b'invalid')
            with self.assertRaises(ValueError): inspector.inspect(p)
            with zipfile.ZipFile(p, 'w') as z: z.writestr('word/document.xml', SAMPLE)
            with self.assertRaisesRegex(ValueError, '缺少必要部件'): inspector.inspect(p)

    def test_invalid_xml_and_dtd_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'bad.docx'; fixture(p, b'<bad>')
            with self.assertRaisesRegex(ValueError, 'XML解析失败'): inspector.inspect(p)
            fixture(p, b'<!DOCTYPE x [<!ENTITY x "danger">]><x>&x;</x>')
            with self.assertRaisesRegex(ValueError, 'DTD'): inspector.inspect(p)

    def test_wrong_root_and_nul_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'bad.docx'; fixture(p, b'<other/>')
            with self.assertRaisesRegex(ValueError, '根元素'): inspector.inspect(p)
            fixture(p, b'\xff\xfe<\x00x\x00/\x00>\x00')
            with self.assertRaisesRegex(ValueError, 'NUL'): inspector.inspect(p)

    def test_duplicate_zip_entry_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'dup.docx'; fixture(p)
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', UserWarning)
                with zipfile.ZipFile(p, 'a') as z: z.writestr('word/document.xml', SAMPLE)
            with self.assertRaisesRegex(ValueError, '重复条目'): inspector.inspect(p)


if __name__ == '__main__':
    unittest.main()
