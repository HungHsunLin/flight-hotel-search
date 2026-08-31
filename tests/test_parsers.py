"""解析層的回歸測試。不需要網路，全部跑在合成資料上（見 fixtures.py）。

    python3 -m unittest discover -s tests -v      # 從專案根目錄執行

測試的是「我們的 regex 有沒有照設計運作」，不是「Google 今天回什麼」。線上壞掉
最常見的原因是 Google 改了措辭——那種情況這裡不會變紅，只能靠實際查詢時的空結果
發現。所以改 locales.py 的 regex 時，仍要用真實頁面對照一次。

多數 case 對應的是實際踩過的坑，每個都在測試名稱與註解裡標明了。
"""
import base64
import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), 'scripts'))

import fixtures  # noqa: E402
import gfparse, ghparse, gtsgen, locales  # noqa: E402

LANGS = ['zh-TW', 'en', 'ja']


class TestFlightParsing(unittest.TestCase):

    def _parse(self, lang):
        return gfparse.parse(fixtures.as_page(fixtures.FLIGHT_LABELS[lang]), lang)

    def testAllLanguagesExtractEveryFlight(self):
        for lang in LANGS:
            with self.subTest(lang=lang):
                self.assertEqual(len(self._parse(lang)),
                                 len(fixtures.FLIGHT_LABELS[lang]))

    def testFieldsAreExtractedCorrectly(self):
        expected_airline = {'zh-TW': '範例航空', 'en': 'Example Air', 'ja': 'サンプル航空'}
        for lang in LANGS:
            with self.subTest(lang=lang):
                row = self._parse(lang)[0]
                self.assertEqual(row['airline'], expected_airline[lang])
                self.assertEqual(row['dep_apt'], 'TPE')
                self.assertEqual(row['arr_apt'], 'NRT')
                self.assertTrue(row['stops'], 'first fixture is a nonstop flight')
                self.assertTrue(row['duration'], 'duration must not be empty')

    def testPriceIsParsedAsIntWithThousandsSeparatorRemoved(self):
        for lang, expected in [('zh-TW', 9999), ('en', 999), ('ja', 99999)]:
            with self.subTest(lang=lang):
                self.assertEqual(self._parse(lang)[0]['price'], expected)

    def testResultsAreSortedByPriceAscending(self):
        for lang in LANGS:
            with self.subTest(lang=lang):
                prices = [r['price'] for r in self._parse(lang)]
                self.assertEqual(prices, sorted(prices))

    def testConnectingFlightIsNotReportedAsNonstop(self):
        # 第二筆 fixture 是轉機航班，不得被當成直達。
        for lang in LANGS:
            with self.subTest(lang=lang):
                self.assertFalse(self._parse(lang)[1]['stops'])

    def testLabelLongerThanFourHundredCharsIsParsedCompletely(self):
        # 擷取長度上限若設得太小，超長的 label 會被靜默切掉尾段（抵達機場、總時長），
        # 而且不會有任何錯誤——只是資料悄悄變少。這裡用一筆 >400 字元的合成樣本
        # 守住上限。實測的真實直飛 label 最長 277 字元，尚未觸及上限；轉機航段
        # 是否更長未經驗證，700 是防禦性餘裕。
        long_label = max(fixtures.FLIGHT_LABELS['en'], key=len)
        self.assertGreater(len(long_label), 400,
                           'fixture must exceed 400 chars or this test proves nothing')
        rows = self._parse('en')
        longest = max(rows, key=lambda r: r['price'])
        self.assertEqual(longest['duration'], '11 hr 45 min',
                         'duration lost = the long label was truncated')
        self.assertFalse(longest['stops'], 'this fixture is a 2-stop flight')

    def testEnglishNarrowNoBreakSpaceInTimeIsHandled(self):
        # 英文時間用 U+202F（窄不斷行空格），不是普通空格。寫死 ' ' 會對不到。
        row = self._parse('en')[0]
        self.assertIn('12:00', row['dep'])
        self.assertIn('PM', row['dep'])

    def testEmptyPageReturnsEmptyListInsteadOfRaising(self):
        for lang in LANGS:
            with self.subTest(lang=lang):
                self.assertEqual(gfparse.parse('<html></html>', lang), [])

    def testUnrelatedLabelsAreIgnored(self):
        # 只有雜訊、沒有航班的頁面不得產生任何列。
        page = fixtures.as_page([])
        for lang in LANGS:
            with self.subTest(lang=lang):
                self.assertEqual(gfparse.parse(page, lang), [])


class TestHotelParsing(unittest.TestCase):

    def _parse(self, lang):
        return ghparse.parse(fixtures.as_page(fixtures.HOTEL_LABELS[lang]), lang)

    def testAllLanguagesExtractEveryHotel(self):
        for lang in LANGS:
            with self.subTest(lang=lang):
                self.assertEqual(len(self._parse(lang)), 2)

    def testRatingIsMatchedToTheRightHotel(self):
        # 價格與評分散在不同 label 裡，靠飯店名配對。三個語系名稱的位置都不同
        # （en 在句尾、ja 在全形括號內、zh 在直角引號內）。
        for lang in LANGS:
            with self.subTest(lang=lang):
                rows = {r['name']: r for r in self._parse(lang)}
                cheap = self._parse(lang)[0]
                self.assertEqual(cheap['stars'], '4.5')
                self.assertEqual(cheap['reviews'], '100')
                self.assertEqual(len(rows), 2)

    def testDealSuffixIsNotSwallowedIntoHotelName(self):
        # 實際踩過的坑：英文的 DEAL 尾綴只隔一個空格，非貪婪比對會把
        # 「Example Hotel DEAL 25% less than usual」整段當成飯店名。
        expected = {'zh-TW': '範例飯店', 'en': 'Example Hotel', 'ja': 'サンプルホテル'}
        for lang in LANGS:
            with self.subTest(lang=lang):
                row = self._parse(lang)[0]
                self.assertEqual(row['name'], expected[lang])
                self.assertEqual(row['deal'], '25%')
                self.assertNotIn('DEAL', row['name'])
                self.assertNotIn('お得', row['name'])
                self.assertNotIn('便宜', row['name'])

    def testHotelWithoutDealHasEmptyDealField(self):
        for lang in LANGS:
            with self.subTest(lang=lang):
                self.assertEqual(self._parse(lang)[1]['deal'], '')

    def testPricesAreSortedAscending(self):
        for lang in LANGS:
            with self.subTest(lang=lang):
                prices = [r['price'] for r in self._parse(lang)]
                self.assertEqual(prices, sorted(prices))

    def testEmptyPageReturnsEmptyList(self):
        for lang in LANGS:
            with self.subTest(lang=lang):
                self.assertEqual(ghparse.parse('<html></html>', lang), [])


class TestAirportCodes(unittest.TestCase):

    def testSameAirportResolvesFromEveryLanguageName(self):
        for name in ['臺灣桃園國際機場', 'Taiwan Taoyuan International Airport', '台湾桃園国際空港']:
            with self.subTest(name=name):
                self.assertEqual(locales.airport_code(name), 'TPE')

    def testHanedaVariantsAllResolve(self):
        for name in ['羽田機場', 'Haneda Airport', '羽田空港', '東京國際機場（羽田機場）']:
            with self.subTest(name=name):
                self.assertEqual(locales.airport_code(name), 'HND')

    def testUnknownAirportFallsBackToTruncatedNameInsteadOfRaising(self):
        self.assertEqual(locales.airport_code('Nowhere Regional Airport'), 'Nowh')
        self.assertEqual(locales.airport_code(''), '?')
        self.assertEqual(locales.airport_code(None), '?')


class TestDisplayWidth(unittest.TestCase):
    """CJK 全形字元佔兩格。用 len() 對齊，中日文欄位會整排跑掉。"""

    def testFullWidthCharactersCountAsTwoColumns(self):
        self.assertEqual(locales.dwidth('abc'), 3)
        self.assertEqual(locales.dwidth('金澤'), 4)
        self.assertEqual(locales.dwidth('金澤hotel'), 9)

    def testPaddedStringsAllReachTheSameDisplayWidth(self):
        for s in ['Example Hotel', '範例飯店', 'サンプルホテル', 'KOKO 金沢']:
            with self.subTest(s=s):
                self.assertEqual(locales.dwidth(locales.dpad(s, 20)), 20)

    def testTruncationDoesNotSplitAFullWidthCharacter(self):
        # 寬度 5 放不下第三個全形字，結果應是 2 個字（寬 4），不是切半個字元。
        self.assertEqual(locales.dtrunc('金澤站前', 5), '金澤')
        self.assertLessEqual(locales.dwidth(locales.dtrunc('金澤站前', 5)), 5)

    def testRightAlignPadsOnTheLeft(self):
        self.assertTrue(locales.dpad('12', 5, '>').startswith('   '))


class TestLocaleResolution(unittest.TestCase):

    def testKnownLanguagesResolveToThemselves(self):
        for lang in LANGS:
            with self.subTest(lang=lang):
                self.assertEqual(locales.resolve(lang)[0], lang)

    def testUnknownLanguageFallsBackToDefaultInsteadOfRaising(self):
        # 未知語系必須降級而不是炸掉——查詢仍該可用，只是介面語言不同。
        for lang in ['fr', 'klingon', '', None]:
            with self.subTest(lang=lang):
                self.assertEqual(locales.resolve(lang)[0], locales.DEFAULT)

    def testEveryLocaleDefinesTheSameUiKeys(self):
        # 少一個 key 會在執行到那條路徑時才 KeyError，通常是錯誤處理路徑——
        # 剛好是最少被走到、最晚被發現的地方。
        reference = set(locales.get('zh-TW')['ui'])
        for lang in LANGS:
            with self.subTest(lang=lang):
                self.assertEqual(set(locales.get(lang)['ui']), reference)

    def testEveryLocaleDefinesTheSameStructuralKeys(self):
        reference = set(locales.get('zh-TW'))
        for lang in LANGS:
            with self.subTest(lang=lang):
                self.assertEqual(set(locales.get(lang)), reference)

    def testCurrencySymbolFallsBackToTheCodeItself(self):
        self.assertEqual(locales.symbol_for('TWD'), 'NT$')
        self.assertEqual(locales.symbol_for('JPY'), '¥')
        self.assertEqual(locales.symbol_for('XYZ'), 'XYZ ')
        self.assertIsNone(locales.symbol_for(None))


class TestTsParameter(unittest.TestCase):
    """ts 是 Hotels 唯一真正生效的日期/幣別/人數來源，URL 參數會被忽略。"""

    def _raw(self, **kw):
        args = dict(kgid='', name='', ci=(2026, 11, 24), co=(2026, 11, 26))
        args.update(kw)
        ts = gtsgen.make_ts(**args)
        return base64.urlsafe_b64decode(ts + '=' * (-len(ts) % 4))

    def testCurrencyIsEncodedIntoTs(self):
        # URL 的 curr= 對 Hotels 無效；少了這段，不論查詢幣別一律回 TWD 報價。
        self.assertIn(b'USD', self._raw(curr='USD'))
        self.assertIn(b'JPY', self._raw(curr='JPY'))
        self.assertNotIn(b'USD', self._raw(curr='TWD'))

    def testOccupancyIsEncodedAsRepeatedFieldNotACount(self):
        # 人數是「重複 field 的次數」，不是把數字寫進某個欄位。寫成數字 Google
        # 會靜默忽略、一律回 2 人房價。
        self.assertNotEqual(self._raw(adults=1), self._raw(adults=2))
        self.assertNotEqual(self._raw(adults=2), self._raw(adults=4))

    def testDifferentDatesProduceDifferentTs(self):
        a = self._raw(ci=(2026, 11, 24), co=(2026, 11, 26))
        b = self._raw(ci=(2026, 12, 30), co=(2027, 1, 3))
        self.assertNotEqual(a, b)

    def testTsIsUrlSafeBase64WithoutPadding(self):
        ts = gtsgen.make_ts('', '', (2026, 11, 24), (2026, 11, 26))
        self.assertNotIn('=', ts)
        self.assertNotIn('+', ts)
        self.assertNotIn('/', ts)


class TestRendering(unittest.TestCase):

    def testFlightRenderProducesOutputInEveryLanguage(self):
        for lang in LANGS:
            with self.subTest(lang=lang):
                rows = gfparse.parse(fixtures.as_page(fixtures.FLIGHT_LABELS[lang]), lang)
                out = gfparse.render(rows, lang=lang)
                self.assertIn('TPE-NRT', out)
                self.assertTrue(out.strip())

    def testHotelRenderProducesOutputInEveryLanguage(self):
        for lang in LANGS:
            with self.subTest(lang=lang):
                rows = ghparse.parse(fixtures.as_page(fixtures.HOTEL_LABELS[lang]), lang)
                out = ghparse.render(rows, lang=lang)
                self.assertIn('4.5', out)

    def testEmptyResultRendersLocalisedNoDataMessageInsteadOfCrashing(self):
        for lang in LANGS:
            with self.subTest(lang=lang):
                self.assertEqual(gfparse.render([], lang=lang), locales.get(lang)['ui']['no_data_flight'])
                self.assertEqual(ghparse.render([], lang=lang), locales.get(lang)['ui']['no_data_hotel'])

    def testCurrencySymbolOverrideIsHonoured(self):
        rows = gfparse.parse(fixtures.as_page(fixtures.FLIGHT_LABELS['en']), 'en')
        self.assertIn('¥', gfparse.render(rows, lang='en', symbol='¥'))


class TestHotelTotals(unittest.TestCase):
    """住宿總價的擷取與配對。

    總價是唯一不靠飯店名配對的欄位——節點本身不帶名稱，只能靠版面位置錨定。
    配對錯誤的後果是「每個數字都合法、但屬於別間飯店」，畫面上完全看不出來，
    所以這裡的重點不是「有沒有抓到」，而是「有沒有配到正確的那一間」。
    """

    def testHotelTotalWhenPageHasTotalNodesThenEveryHotelGetsOne(self):
        for lang in LANGS:
            with self.subTest(lang=lang):
                # Given: 一頁含總價節點的飯店結果
                page = fixtures.as_hotel_page(lang)
                # When: 解析
                rows = ghparse.parse(page, lang)
                # Then: 每一筆都有總價，且晚數讀得到
                self.assertTrue(all(r['total'] for r in rows))
                self.assertTrue(all(r['nights'] == fixtures.HOTEL_NIGHTS for r in rows))

    def testHotelTotalWhenTwoHotelsDifferThenEachKeepsItsOwnTotal(self):
        # Given: 兩張卡片的總價設成一眼可辨的數字，且刻意不等於每晚 × 晚數——
        # 若用真實比例，配錯時算出來的數字仍會「看起來合理」，測不出錯位。
        cards = [(price_lab, total, rating_lab)
                 for (price_lab, _, rating_lab), total
                 in zip(fixtures.HOTEL_CARDS['zh-TW'], ['11,111', '22,222'])]
        # When: 解析
        rows = ghparse.parse(fixtures.as_hotel_page('zh-TW', cards=cards), 'zh-TW')
        # Then: 每筆總價都留在自己那張卡片上，沒有漂到隔壁
        self.assertEqual({'範例飯店': 11111, '測試旅館': 22222},
                         {r['name']: r['total'] for r in rows})

    def testHotelTotalWhenTotalsAreSwappedThenMismatchIsReported(self):
        # Given: 一頁的總價刻意與每晚房價對不上（模擬版面改動導致配對錯位）
        cards = [(p, t, r) for (p, _, r), t in
                 zip(fixtures.HOTEL_CARDS['zh-TW'], ['12,340', '6,170'])]
        page = fixtures.as_hotel_page('zh-TW', cards=cards)
        # When: 解析並核帳
        rows = ghparse.parse(page, 'zh-TW')
        # Then: 兩筆都被指認出來，而且輸出裡有警告
        self.assertEqual(2, ghparse.mismatched(rows))
        self.assertIn('⚠️', ghparse.render(rows, lang='zh-TW'))

    def testHotelTotalWhenCardHasTwoDifferentTotalsThenTheNearerOneWins(self):
        # Given: 同一張卡片內出現兩個不同的總價節點。
        # 真實頁面重複的兩筆數值相同，所以「取第一筆」與「取最後一筆」看不出差別——
        # 必須讓兩筆不同，才測得到 setdefault 的語意（取最靠近價格 label 的那筆）。
        node = fixtures.HOTEL_TOTAL_NODES['zh-TW']
        price_lab, _, rating_lab = fixtures.HOTEL_CARDS['zh-TW'][0]
        page = ('<html><body>'
                f'<div aria-label="{price_lab}"></div>'
                + node.format(t='11,111', n=5)
                + node.format(t='99,999', n=5)
                + f'<div aria-label="{rating_lab}"></div></body></html>')
        # When: 解析
        rows = ghparse.parse(page, 'zh-TW')
        # Then: 取的是前面那筆，不是後來覆蓋上去的
        self.assertEqual(11111, rows[0]['total'])

    def testHotelTotalWhenPageHasNoTotalNodesThenParsingStillSucceeds(self):
        for lang in LANGS:
            with self.subTest(lang=lang):
                # Given: 舊版面（只有 aria-label、沒有總價節點）
                page = fixtures.as_page(fixtures.HOTEL_LABELS[lang])
                # When: 解析
                rows = ghparse.parse(page, lang)
                # Then: 仍解析得出飯店，總價留白而不是硬用乘法頂替
                self.assertTrue(rows)
                self.assertTrue(all(r['total'] == 0 for r in rows))
                self.assertEqual(0, ghparse.mismatched(rows))

    def testHotelNameWhenLabelUsesGreatDealSuffixThenSuffixIsNotSwallowed(self):
        # Given: 英文大折扣的尾綴是 GREAT DEAL 而不是 DEAL
        page = fixtures.as_hotel_page('en')
        # When: 解析
        rows = ghparse.parse(page, 'en')
        names = [r['name'] for r in rows]
        # Then: 名稱乾淨，且因此配得到評分——名稱被污染時會靜默失去評分
        self.assertIn('Example Hotel', names)
        self.assertNotIn('Example Hotel GREAT', names)
        self.assertEqual('4.5', next(r['stars'] for r in rows if r['name'] == 'Example Hotel'))

    def testHotelRenderWhenTotalsExistThenTotalColumnAppears(self):
        for lang in LANGS:
            with self.subTest(lang=lang):
                rows = ghparse.parse(fixtures.as_hotel_page(lang), lang)
                out = ghparse.render(rows, lang=lang)
                self.assertIn(locales.get(lang)['ui']['total'], out)

if __name__ == '__main__':
    unittest.main(verbosity=2)
