from django.core.management.base import BaseCommand
from django.utils import timezone
from places.models import (
    Literature,
    PlaceName,
    PlaceNameLiterature,
    NameRelation,
    CollationNote,
    Dispute,
)


class Command(BaseCommand):
    help = '填充测试数据'

    def handle(self, *args, **options):
        self.stdout.write('开始填充测试数据...')

        if Literature.objects.exists():
            self.stdout.write(self.style.WARNING('数据已存在，跳过填充。如需重新填充，请先清空数据库。'))
            return

        self._create_literatures()
        self._create_places()
        self._create_relations()
        self._create_collation_notes()
        self._create_disputes()

        self.stdout.write(self.style.SUCCESS('测试数据填充完成！'))

    def _create_literatures(self):
        literatures_data = [
            {
                'title': '元和郡县图志',
                'author': '李吉甫',
                'dynasty': '唐代',
                'publisher': '中华书局',
                'volume': '一',
                'page': '25',
                'note': '唐代地理总志，是现存最早的地方总志',
            },
            {
                'title': '太平寰宇记',
                'author': '乐史',
                'dynasty': '宋代',
                'publisher': '中华书局',
                'volume': '三',
                'page': '67',
                'note': '北宋地理总志',
            },
            {
                'title': '读史方舆纪要',
                'author': '顾祖禹',
                'dynasty': '清代',
                'publisher': '中华书局',
                'volume': '十',
                'page': '128',
                'note': '清初历史地理名著',
            },
            {
                'title': '水经注',
                'author': '郦道元',
                'dynasty': '北魏',
                'publisher': '中华书局',
                'volume': '四',
                'page': '89',
                'note': '古代地理名著，记载河流水道',
            },
            {
                'title': '长安志',
                'author': '宋敏求',
                'dynasty': '宋代',
                'publisher': '中华书局',
                'volume': '二',
                'page': '34',
                'note': '记载长安城的地方志',
            },
            {
                'title': '洛阳伽蓝记',
                'author': '杨衒之',
                'dynasty': '北魏',
                'publisher': '中华书局',
                'volume': '一',
                'page': '56',
                'note': '记载北魏洛阳佛寺的地理著作',
            },
            {
                'title': '舆地广记',
                'author': '欧阳忞',
                'dynasty': '宋代',
                'publisher': '中华书局',
                'volume': '五',
                'page': '78',
                'note': '北宋历史地理总志',
            },
            {
                'title': '方舆胜览',
                'author': '祝穆',
                'dynasty': '宋代',
                'publisher': '中华书局',
                'volume': '七',
                'page': '102',
                'note': '南宋地理总志',
            },
        ]

        for data in literatures_data:
            Literature.objects.create(**data)

        self.stdout.write(f'  - 创建了 {Literature.objects.count()} 条文献记录')

    def _create_places(self):
        literatures = {lit.title: lit for lit in Literature.objects.all()}

        places_data = [
            {
                'name': '长安',
                'alternative_name': '西京',
                'region': '陕西省西安市',
                'start_year': '西汉',
                'end_year': '唐代',
                'reliability': 95,
                'description': '长安是中国历史上建都时间最长、建都朝代最多的古都。西汉、隋、唐等朝代均在此建都。',
                'collation_status': 'completed',
                'longitude': 108.94,
                'latitude': 34.27,
                'literatures': [
                    ('元和郡县图志', '见于卷一，第25页'),
                    ('长安志', '见于卷二，详细记载唐代长安'),
                    ('太平寰宇记', '见于卷三'),
                ],
            },
            {
                'name': '咸阳',
                'alternative_name': '渭城',
                'region': '陕西省咸阳市',
                'start_year': '秦代',
                'end_year': '汉代',
                'reliability': 90,
                'description': '咸阳是秦国都城，秦始皇统一六国后仍以咸阳为都。',
                'collation_status': 'completed',
                'longitude': 108.72,
                'latitude': 34.33,
                'literatures': [
                    ('读史方舆纪要', '见于卷十'),
                    ('水经注', '记载渭水流域'),
                ],
            },
            {
                'name': '洛阳',
                'alternative_name': '洛邑、东都',
                'region': '河南省洛阳市',
                'start_year': '东周',
                'end_year': '宋代',
                'reliability': 92,
                'description': '洛阳是中国历史上重要的古都，东周、东汉、北魏、隋（炀帝）、武周等在此建都。',
                'collation_status': 'completed',
                'longitude': 112.45,
                'latitude': 34.62,
                'literatures': [
                    ('洛阳伽蓝记', '记载北魏洛阳城'),
                    ('元和郡县图志', '见于卷一'),
                    ('太平寰宇记', '见于卷三'),
                ],
            },
            {
                'name': '汴州',
                'alternative_name': '开封、东京',
                'region': '河南省开封市',
                'start_year': '战国',
                'end_year': '宋代',
                'reliability': 88,
                'description': '汴州即开封，战国时为魏国都城大梁，北宋时为东京开封府。',
                'collation_status': 'in_progress',
                'longitude': 114.35,
                'latitude': 34.80,
                'literatures': [
                    ('太平寰宇记', '见于卷三'),
                    ('舆地广记', '见于卷五'),
                ],
            },
            {
                'name': '金陵',
                'alternative_name': '建康、建业、江宁',
                'region': '江苏省南京市',
                'start_year': '三国',
                'end_year': '明代',
                'reliability': 93,
                'description': '金陵是南京的古称，东吴、东晋、宋齐梁陈（六朝）、南唐、明初皆建都于此。',
                'collation_status': 'completed',
                'longitude': 118.78,
                'latitude': 32.06,
                'literatures': [
                    ('读史方舆纪要', '见于卷十'),
                    ('太平寰宇记', '见于卷三'),
                    ('方舆胜览', '见于卷七'),
                ],
            },
            {
                'name': '临安',
                'alternative_name': '杭州、武林',
                'region': '浙江省杭州市',
                'start_year': '隋代',
                'end_year': '宋代',
                'reliability': 85,
                'description': '临安是南宋都城，即今杭州。',
                'collation_status': 'in_progress',
                'longitude': 120.15,
                'latitude': 30.28,
                'literatures': [
                    ('方舆胜览', '见于卷七'),
                    ('舆地广记', '见于卷五'),
                ],
            },
            {
                'name': '邺城',
                'alternative_name': '邺都',
                'region': '河北省临漳县',
                'start_year': '三国',
                'end_year': '北齐',
                'reliability': 80,
                'description': '邺城是三国时期曹魏的五都之一，后赵、前燕、东魏、北齐相继在此建都。',
                'collation_status': 'pending',
                'longitude': 114.63,
                'latitude': 36.37,
                'literatures': [
                    ('读史方舆纪要', '见于卷十'),
                    ('水经注', '记载漳水流域'),
                ],
            },
            {
                'name': '大兴城',
                'alternative_name': '长安',
                'region': '陕西省西安市',
                'start_year': '隋代',
                'end_year': '唐代',
                'reliability': 87,
                'description': '隋朝建立后，在汉长安城东南龙首原南坡修建新都大兴城，唐代改称长安城。',
                'collation_status': 'in_progress',
                'longitude': 108.95,
                'latitude': 34.22,
                'literatures': [
                    ('长安志', '详细记载大兴城的修建'),
                    ('元和郡县图志', '见于卷一'),
                ],
            },
            {
                'name': '大都',
                'alternative_name': '北平、燕京',
                'region': '北京市',
                'start_year': '元代',
                'end_year': '元代',
                'reliability': 91,
                'description': '元大都，即元朝都城，在今北京。元代以前此地称燕京、中都等。',
                'collation_status': 'completed',
                'longitude': 116.40,
                'latitude': 39.90,
                'literatures': [
                    ('读史方舆纪要', '见于卷十'),
                ],
            },
            {
                'name': '成都',
                'alternative_name': '锦官城、蓉城',
                'region': '四川省成都市',
                'start_year': '古蜀',
                'end_year': '',
                'reliability': 94,
                'description': '成都自古以来就是西南地区的重要城市，古蜀国、蜀汉、前蜀、后蜀等政权在此建都。',
                'collation_status': 'completed',
                'longitude': 104.07,
                'latitude': 30.67,
                'literatures': [
                    ('元和郡县图志', '见于卷一'),
                    ('太平寰宇记', '见于卷三'),
                    ('方舆胜览', '见于卷七'),
                ],
            },
        ]

        for data in places_data:
            lits = data.pop('literatures', [])
            place = PlaceName.objects.create(**data)
            for lit_title, citation in lits:
                if lit_title in literatures:
                    PlaceNameLiterature.objects.create(
                        place_name=place,
                        literature=literatures[lit_title],
                        citation_detail=citation
                    )

        self.stdout.write(f'  - 创建了 {PlaceName.objects.count()} 条地名记录')

    def _create_relations(self):
        places = {p.name: p for p in PlaceName.objects.all()}

        relations_data = [
            {
                'name_a': '长安',
                'name_b': '大兴城',
                'relation_type': 'evolution',
                'reliability': 90,
                'confirmed': True,
                'description': '隋代建大兴城，唐代改称长安，实为同一座城市的不同时期名称。',
            },
            {
                'name_a': '长安',
                'name_b': '咸阳',
                'relation_type': 'other',
                'reliability': 75,
                'confirmed': True,
                'description': '咸阳与长安相距不远，秦都咸阳，汉都长安，两地有密切的历史关联。',
            },
            {
                'name_a': '金陵',
                'name_b': '临安',
                'relation_type': 'other',
                'reliability': 70,
                'confirmed': False,
                'description': '金陵与临安分别为南宋前后的重要都城，有一定历史关联。',
            },
            {
                'name_a': '洛阳',
                'name_b': '汴州',
                'relation_type': 'other',
                'reliability': 72,
                'confirmed': True,
                'description': '洛阳与汴州均为中原地区重要古都，自隋唐至北宋，政治中心逐渐东移。',
            },
            {
                'name_a': '邺城',
                'name_b': '洛阳',
                'relation_type': 'other',
                'reliability': 68,
                'confirmed': False,
                'description': '邺城与洛阳同为北朝时期重要城市，北魏后期迁都洛阳。',
            },
            {
                'name_a': '大都',
                'name_b': '临安',
                'relation_type': 'other',
                'reliability': 65,
                'confirmed': False,
                'description': '元大都与南宋临安，元代统一全国后，政治中心北移。',
            },
            {
                'name_a': '成都',
                'name_b': '金陵',
                'relation_type': 'other',
                'reliability': 60,
                'confirmed': False,
                'description': '成都与金陵历史上均为重要地方政权都城。',
            },
            {
                'name_a': '咸阳',
                'name_b': '洛阳',
                'relation_type': 'other',
                'reliability': 73,
                'confirmed': True,
                'description': '咸阳（秦）与洛阳（东周、东汉）均为著名古都，东西二京格局的雏形。',
            },
        ]

        for data in relations_data:
            name_a = places.get(data['name_a'])
            name_b = places.get(data['name_b'])
            if name_a and name_b:
                rel = NameRelation(
                    name_a=name_a,
                    name_b=name_b,
                    relation_type=data['relation_type'],
                    reliability=data['reliability'],
                    confirmed=data['confirmed'],
                    description=data['description'],
                )
                rel.save()

        count = NameRelation.objects.count()
        self.stdout.write(f'  - 创建了 {count} 条异名关系记录')

    def _create_collation_notes(self):
        places = {p.name: p for p in PlaceName.objects.all()}

        notes_data = [
            {
                'place_name': '长安',
                'title': '长安名称沿革考',
                'content': '长安之名始于汉高祖五年（前202年），置长安县，七年迁都于此。长安本为秦代一个乡聚之名，因长安君而得名。',
                'conclusion': '长安地名来源可靠，历史沿革清晰。',
                'collator': '张教授',
            },
            {
                'place_name': '洛阳',
                'title': '洛邑与洛阳关系辩证',
                'content': '洛邑为西周时期的名称，洛阳之名始于战国时期。汉代设洛阳县，以在洛水之阳得名。',
                'conclusion': '洛邑与洛阳实为一地，只是不同时期的名称。',
                'collator': '李研究员',
            },
            {
                'place_name': '金陵',
                'title': '金陵名称来源考证',
                'content': '金陵之名的来源有多种说法：一说因楚威王埋金镇王气得名；一说因金陵山（即今钟山）得名。',
                'conclusion': '金陵名称来源尚无定论，有待进一步考证。',
                'collator': '王教授',
            },
            {
                'place_name': '汴州',
                'title': '大梁与汴州关系',
                'content': '大梁为战国魏国都城，秦灭魏后设浚仪县。南北朝时期置梁州，后改汴州。',
                'conclusion': '汴州是在大梁故地基础上发展起来的，但城址有一定变化。',
                'collator': '赵研究员',
            },
            {
                'place_name': '成都',
                'title': '成都名称含义',
                'content': '关于成都之名的含义，有\"一年成邑，二年成都\"之说，但此说恐为附会。更可能为古蜀语音译。',
                'conclusion': '成都地名来源有待进一步研究。',
                'collator': '陈教授',
            },
        ]

        for data in notes_data:
            place = places.get(data['place_name'])
            if place:
                note_data = {k: v for k, v in data.items() if k != 'place_name'}
                CollationNote.objects.create(place_name=place, **note_data)

        count = CollationNote.objects.count()
        self.stdout.write(f'  - 创建了 {count} 条校勘意见记录')

    def _create_disputes(self):
        places = {p.name: p for p in PlaceName.objects.all()}

        disputes_data = [
            {
                'place_name': '金陵',
                'title': '金陵名称来源争议',
                'content': '关于金陵名称的来源，学术界主要有两种观点：一种认为来源于楚威王埋金的传说；另一种认为因金陵山（钟山）得名。目前尚无定论。',
                'proposer': '王教授',
                'status': 'open',
                'resolution': '',
            },
            {
                'place_name': '临安',
                'title': '南宋是否以临安为正式都城',
                'content': '一种观点认为南宋名义上仍以开封为都城，临安只是\"行在所\"（临时驻地）；另一种观点认为临安实际上就是南宋的正式都城。',
                'proposer': '钱研究员',
                'status': 'open',
                'resolution': '',
            },
            {
                'place_name': '成都',
                'title': '成都建城时间争议',
                'content': '关于成都建城的具体时间，有古蜀国开明王朝时期和秦灭蜀后张仪筑城两种不同说法。',
                'proposer': '陈教授',
                'status': 'resolved',
                'resolution': '一般认为张仪筑成都城是有明确记载的建城史，但此前古蜀国已在此建都。',
            },
            {
                'place_name': '邺城',
                'title': '邺城具体位置考辨',
                'content': '关于邺城的具体位置，传统认为在今临漳县西南，但近年来有学者提出不同看法，认为遗址位置需要重新确认。',
                'proposer': '孙研究员',
                'status': 'open',
                'resolution': '',
            },
            {
                'place_name': '大兴城',
                'title': '大兴城与汉长安城的继承关系',
                'content': '大兴城（唐长安城）是否完全新建，还是在汉长安城基础上扩建，学术界存在不同意见。',
                'proposer': '李教授',
                'status': 'resolved',
                'resolution': '经考古确认，大兴城为新建城市，位于汉长安城东南方向，并非在其基础上扩建。',
            },
        ]

        for data in disputes_data:
            place = places.get(data['place_name'])
            if place:
                dispute_data = {k: v for k, v in data.items() if k != 'place_name'}
                Dispute.objects.create(place_name=place, **dispute_data)

        count = Dispute.objects.count()
        self.stdout.write(f'  - 创建了 {count} 条争议记录')
