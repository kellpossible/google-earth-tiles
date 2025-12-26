"""Configuration for WMTS layers and application settings."""

from dataclasses import dataclass


@dataclass(frozen=True)
class LayerCategory:
    """Category for grouping layers."""

    id: str
    name_en: str
    name_ja: str


# Layer categories
CATEGORIES: dict[str, LayerCategory] = {
    "basemap": LayerCategory(id="basemap", name_en="Base Maps", name_ja="ベースマップ"),
    "photo": LayerCategory(id="photo", name_en="Aerial Photos", name_ja="年代別の写真"),
    "elevation": LayerCategory(id="elevation", name_en="Elevation & Terrain", name_ja="標高・土地の凹凸"),
    "landuse": LayerCategory(id="landuse", name_en="Land Formation & Land Use", name_ja="土地の成り立ち・土地利用"),
    "reference": LayerCategory(
        id="reference", name_en="Reference Points & Geomagnetism", name_ja="基準点・地磁気・地殻変動"
    ),
    "disaster_eq": LayerCategory(
        id="disaster_eq", name_en="Recent Disasters - Earthquakes", name_ja="近年の災害 - 地震"
    ),
    "disaster_weather": LayerCategory(
        id="disaster_weather", name_en="Recent Disasters - Weather", name_ja="近年の災害 - 台風・豪雨等"
    ),
    "disaster_volcano": LayerCategory(
        id="disaster_volcano", name_en="Recent Disasters - Volcanoes", name_ja="近年の災害 - 火山"
    ),
    "other": LayerCategory(id="other", name_en="Other", name_ja="その他"),
}


@dataclass(frozen=True)
class LayerConfig:
    """Configuration for a tile layer.

    Supports both WMTS sources (via name parameter for GSI) and custom tile URLs.
    """

    name: str
    display_name: str
    extension: str
    min_zoom: int
    max_zoom: int
    description: str
    japanese_name: str
    full_description: str
    info_url: str
    category: str
    custom_url_template: str | None = None

    @property
    def url_template(self) -> str:
        """Get the URL template for this layer.

        Uses custom_url_template if provided, otherwise generates GSI WMTS URL.
        """
        if self.custom_url_template:
            return self.custom_url_template
        return f"https://maps.gsi.go.jp/xyz/{self.name}/{{z}}/{{x}}/{{y}}.{self.extension}"


# Available WMTS layers from Japan GSI
LAYERS: dict[str, LayerConfig] = {
    "std": LayerConfig(
        name="std",
        display_name="Standard Map",
        extension="png",
        min_zoom=2,
        max_zoom=18,
        description="Standard map with roads and labels",
        japanese_name="標準地図",
        full_description="Electronic topographic map with standard cartographic styling. "
        "Shows detailed road networks, building outlines, geographic labels, "
        "elevation contours, and administrative boundaries. Suitable for general "
        "reference mapping across Japan and surrounding regions.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="basemap",
    ),
    "pale": LayerConfig(
        name="pale",
        display_name="Pale Map",
        extension="png",
        min_zoom=2,
        max_zoom=18,
        description="Pale colored base map",
        japanese_name="淡色地図",
        full_description="Lighter-toned version of the standard map designed specifically for use as "
        "a background layer beneath thematic overlays. The reduced color intensity "
        "allows custom data visualizations to stand out while maintaining essential "
        "geographic context.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="basemap",
    ),
    "english": LayerConfig(
        name="english",
        display_name="English Map",
        extension="png",
        min_zoom=5,
        max_zoom=8,
        description="Map with English labels",
        japanese_name="English",
        full_description="International map of Japan with English labeling for place names, features, "
        "and geographic regions. Designed for international reference, tourism "
        "applications, and global users requiring romanized toponymy.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="basemap",
    ),
    "ort": LayerConfig(
        name="ort",
        display_name="Orthographic Aerial Photos",
        extension="jpg",
        min_zoom=2,
        max_zoom=18,
        description="Corrected aerial photography",
        japanese_name="電子国土基本図（オルソ画像）",
        full_description="Geometrically corrected aerial photographs captured from 2007 onwards. "
        "These orthophotos provide high-precision geospatial reference imagery "
        "suitable for accurate measurement, analysis, and overlay with other datasets. "
        "Updated regularly to reflect current ground conditions.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="photo",
    ),
    "relief": LayerConfig(
        name="relief",
        display_name="Color-Coded Elevation Map",
        extension="png",
        min_zoom=5,
        max_zoom=15,
        description="Elevation shown through color gradation",
        japanese_name="色別標高図",
        full_description="Topographic visualization displaying elevation through color gradation and "
        "shading effects. Higher elevations appear in warmer colors while lower areas "
        "use cooler tones, making terrain features and landforms immediately apparent. "
        "Useful for understanding regional topography and terrain characteristics.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="elevation",
    ),
    "seamlessphoto": LayerConfig(
        name="seamlessphoto",
        display_name="Seamless Aerial Photos",
        extension="jpg",
        min_zoom=2,
        max_zoom=18,
        description="Composite recent aerial imagery",
        japanese_name="シームレス空中写真",
        full_description="Composite aerial imagery created by seamlessly combining the most recent "
        "photographs from various sources maintained by the Geospatial Information "
        "Authority of Japan. Provides nationwide coverage showing current ground "
        "conditions, land use patterns, and development status.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="photo",
    ),
    "blank": LayerConfig(
        name="blank",
        display_name="Blank Map",
        extension="png",
        min_zoom=5,
        max_zoom=14,
        description="Simplified map with boundaries only",
        japanese_name="白地図",
        full_description="A simplified basemap displaying Japan's national outline and administrative "
        "boundaries without detailed geographic features. Suitable as a base layer for "
        "custom mapping projects and data visualization.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="basemap",
    ),
    "hillshademap": LayerConfig(
        name="hillshademap",
        display_name="Hillshade Map",
        extension="png",
        min_zoom=2,
        max_zoom=16,
        description="Terrain relief using shadow effects",
        japanese_name="陰影起伏図",
        full_description="Map that visualizes terrain relief using hill shading based on elevation data "
        "from the Fundamental Geospatial Data numerical elevation model. Effective for "
        "understanding topographic features and terrain comprehension.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="elevation",
    ),
    "slopemap": LayerConfig(
        name="slopemap",
        display_name="Slope Map",
        extension="png",
        min_zoom=3,
        max_zoom=15,
        description="Terrain slope steepness",
        japanese_name="傾斜量図",
        full_description="Depicts terrain slope steepness using the Fundamental Geospatial Data numerical "
        "elevation model. Effective for identifying areas prone to landslides and other "
        "slope-related hazards.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="elevation",
    ),
    "lcm25k": LayerConfig(
        name="lcm25k",
        display_name="Land Condition Map",
        extension="png",
        min_zoom=14,
        max_zoom=16,
        description="Digitized land condition survey",
        japanese_name="土地条件図",
        full_description="Digitized land condition survey data showing terrain classification. Provides "
        "detailed information about land formation, surface geology, and natural features "
        "at high zoom levels.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="landuse",
    ),
    "sekishoku": LayerConfig(
        name="sekishoku",
        display_name="Red Relief Map",
        extension="png",
        min_zoom=2,
        max_zoom=14,
        description="Microtopography visualization",
        japanese_name="赤色立体地図",
        full_description="Microtopography visualization using red intensity gradations. This unique "
        "representation makes subtle terrain features, archaeological sites, and "
        "geomorphological structures easily visible.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="elevation",
    ),
    # Land Formation & Land Use Maps
    "lcm25k_2012": LayerConfig(
        name="lcm25k_2012",
        display_name="Land Conditions Map 2012",
        extension="png",
        min_zoom=10,
        max_zoom=16,
        description="Numerical map 25k land conditions",
        japanese_name="数値地図25000（土地条件）",
        full_description="Digital land condition survey data from 2012 showing terrain classification, "
        "surface geology, and natural features.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="landuse",
    ),
    "ccm1": LayerConfig(
        name="ccm1",
        display_name="Coastal Land Condition Map",
        extension="png",
        min_zoom=14,
        max_zoom=16,
        description="Coastal land conditions",
        japanese_name="沿岸海域土地条件図",
        full_description="Land condition map for coastal areas showing terrain classification and "
        "geomorphological features of coastal zones.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="landuse",
    ),
    "ccm2": LayerConfig(
        name="ccm2",
        display_name="Coastal Land Condition Map (Pre-1988)",
        extension="png",
        min_zoom=14,
        max_zoom=16,
        description="Coastal land conditions prior to 1988",
        japanese_name="沿岸海域土地条件図（昭和63年以前）",
        full_description="Historical coastal land condition map showing geological and topographic "
        "features prior to 1988.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="landuse",
    ),
    "vbm": LayerConfig(
        name="vbm",
        display_name="Volcano Base Map",
        extension="png",
        min_zoom=11,
        max_zoom=17,
        description="Volcanic area base map",
        japanese_name="火山基本図",
        full_description="Specialized topographic maps of volcanic areas showing terrain features, "
        "geological formations, and volcanic structures.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="landuse",
    ),
    "vbmd_bm": LayerConfig(
        name="vbmd_bm",
        display_name="Volcano Data - Base Map",
        extension="png",
        min_zoom=11,
        max_zoom=18,
        description="Volcano base map data",
        japanese_name="火山基本図データ（基図）",
        full_description="Digital volcano base map data with detailed topographic information.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="landuse",
    ),
    "vbmd_colorrel": LayerConfig(
        name="vbmd_colorrel",
        display_name="Volcano Data - Shaded Relief",
        extension="png",
        min_zoom=11,
        max_zoom=18,
        description="Volcano shaded relief",
        japanese_name="火山基本図データ（陰影段彩図）",
        full_description="Volcano maps with shaded relief and color-coded elevation.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="landuse",
    ),
    "vbmd_pm": LayerConfig(
        name="vbmd_pm",
        display_name="Volcano Data - Photo Map",
        extension="png",
        min_zoom=11,
        max_zoom=18,
        description="Volcano aerial photo map",
        japanese_name="火山基本図データ（写真地図）",
        full_description="Aerial photography of volcanic areas.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="landuse",
    ),
    "vlcd": LayerConfig(
        name="vlcd",
        display_name="Volcano Land Condition Map",
        extension="png",
        min_zoom=10,
        max_zoom=16,
        description="Volcanic land conditions",
        japanese_name="火山土地条件図",
        full_description="Land condition classification for volcanic areas.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="landuse",
    ),
    "lum200k": LayerConfig(
        name="lum200k",
        display_name="Land Use Map 1:200k",
        extension="png",
        min_zoom=11,
        max_zoom=14,
        description="1:200,000 scale land use",
        japanese_name="20万分1土地利用図",
        full_description="Land use classification maps at 1:200,000 scale.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="landuse",
    ),
    "lake1": LayerConfig(
        name="lake1",
        display_name="Lake Map",
        extension="png",
        min_zoom=11,
        max_zoom=17,
        description="Lake survey maps",
        japanese_name="湖沼図",
        full_description="Detailed maps of lakes showing bathymetry and features.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="landuse",
    ),
    "lakedata": LayerConfig(
        name="lakedata",
        display_name="Lake Data",
        extension="png",
        min_zoom=11,
        max_zoom=18,
        description="Lake data layer",
        japanese_name="湖沼データ",
        full_description="Digital lake data with detailed information.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="landuse",
    ),
    # Historical Aerial Photos
    "gazo1": LayerConfig(
        name="gazo1",
        display_name="Aerial Photo 1974-1978",
        extension="jpg",
        min_zoom=10,
        max_zoom=17,
        description="Historical aerial photos 1974-1978",
        japanese_name="1974年～1978年",
        full_description="Historical aerial photographs from 1974 to 1978.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="photo",
    ),
    "gazo2": LayerConfig(
        name="gazo2",
        display_name="Aerial Photo 1979-1983",
        extension="jpg",
        min_zoom=10,
        max_zoom=17,
        description="Historical aerial photos 1979-1983",
        japanese_name="1979年～1983年",
        full_description="Historical aerial photographs from 1979 to 1983.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="photo",
    ),
    "gazo3": LayerConfig(
        name="gazo3",
        display_name="Aerial Photo 1984-1986",
        extension="jpg",
        min_zoom=10,
        max_zoom=17,
        description="Historical aerial photos 1984-1986",
        japanese_name="1984年～1986年",
        full_description="Historical aerial photographs from 1984 to 1986.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="photo",
    ),
    "gazo4": LayerConfig(
        name="gazo4",
        display_name="Aerial Photo 1987-1990",
        extension="jpg",
        min_zoom=10,
        max_zoom=17,
        description="Historical aerial photos 1987-1990",
        japanese_name="1987年～1990年",
        full_description="Historical aerial photographs from 1987 to 1990.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="photo",
    ),
    "ort_old10": LayerConfig(
        name="ort_old10",
        display_name="Aerial Photo 1961-1969",
        extension="png",
        min_zoom=10,
        max_zoom=17,
        description="Historical aerial photos 1961-1969",
        japanese_name="1961年～1969年",
        full_description="Historical aerial photographs from 1961 to 1969.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="photo",
    ),
    "ort_USA10": LayerConfig(
        name="ort_USA10",
        display_name="Aerial Photo 1945-1950 (US)",
        extension="png",
        min_zoom=10,
        max_zoom=17,
        description="US military aerial photos 1945-1950",
        japanese_name="1945年～1950年",
        full_description="Historical aerial photographs taken by US military from 1945 to 1950.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="photo",
    ),
    "ort_riku10": LayerConfig(
        name="ort_riku10",
        display_name="Aerial Photo 1936-1942",
        extension="png",
        min_zoom=13,
        max_zoom=18,
        description="Pre-war aerial photos 1936-1942",
        japanese_name="1936年～1942年頃",
        full_description="Pre-war aerial photographs from approximately 1936 to 1942.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="photo",
    ),
    "ort_1928": LayerConfig(
        name="ort_1928",
        display_name="Aerial Photo c.1928",
        extension="png",
        min_zoom=13,
        max_zoom=18,
        description="Aerial photos circa 1928",
        japanese_name="1928年頃",
        full_description="Historical aerial photographs from approximately 1928.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="photo",
    ),
    "airphoto": LayerConfig(
        name="airphoto",
        display_name="Simple Aerial Photo",
        extension="png",
        min_zoom=14,
        max_zoom=18,
        description="Simple aerial photos 2004+",
        japanese_name="簡易空中写真",
        full_description="Simplified aerial photographs from 2004 onwards.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="photo",
    ),
    "lndst": LayerConfig(
        name="lndst",
        display_name="Landsat Mosaic",
        extension="png",
        min_zoom=2,
        max_zoom=13,
        description="National Landsat satellite mosaic",
        japanese_name="全国ランドサットモザイク画像",
        full_description="Nationwide mosaic imagery from Landsat satellites.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="photo",
    ),
    "modis": LayerConfig(
        name="modis",
        display_name="Global Satellite Mosaic",
        extension="png",
        min_zoom=2,
        max_zoom=8,
        description="World satellite mosaic imagery",
        japanese_name="世界衛星モザイク画像",
        full_description="Global satellite mosaic imagery from MODIS.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="photo",
    ),
    # Post-2011 Earthquake Orthophotos
    "toho1": LayerConfig(
        name="toho1",
        display_name="Post-Earthquake 2011 Mar-Apr",
        extension="jpg",
        min_zoom=15,
        max_zoom=17,
        description="Post-earthquake orthophoto Mar-Apr 2011",
        japanese_name="平成23年東北地方太平洋沖地震後正射画像（2011年3月～2011年4月撮影）",
        full_description="Orthophoto imagery captured following the March 2011 Great East Japan Earthquake, "
        "covering March through April 2011.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="disaster_eq",
    ),
    "toho2": LayerConfig(
        name="toho2",
        display_name="Post-Earthquake 2011 May-2012 Apr",
        extension="jpg",
        min_zoom=15,
        max_zoom=18,
        description="Post-earthquake orthophoto May 2011-Apr 2012",
        japanese_name="平成23年東北地方太平洋沖地震後正射画像（2011年5月～2012年4月撮影）",
        full_description="Post-earthquake orthophoto covering May 2011 through April 2012, documenting "
        "recovery and damage assessment.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="disaster_eq",
    ),
    "toho3": LayerConfig(
        name="toho3",
        display_name="Post-Earthquake 2012 Oct-2013 May",
        extension="jpg",
        min_zoom=15,
        max_zoom=18,
        description="Post-earthquake orthophoto Oct 2012-May 2013",
        japanese_name="平成23年東北地方太平洋沖地震後正射画像（2012年10月～2013年5月撮影）",
        full_description="Orthophoto imagery from October 2012 through May 2013, capturing later "
        "reconstruction phases.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="disaster_eq",
    ),
    "toho4": LayerConfig(
        name="toho4",
        display_name="Post-Earthquake 2013 Sep-Dec",
        extension="jpg",
        min_zoom=15,
        max_zoom=18,
        description="Post-earthquake orthophoto Sep-Dec 2013",
        japanese_name="平成23年東北地方太平洋沖地震後正射画像（2013年9月～2013年12月撮影）",
        full_description="Final post-earthquake orthophoto series from September through December 2013, "
        "showing continued reconstruction.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="disaster_eq",
    ),
    # Additional Terrain Maps
    "earthhillshade": LayerConfig(
        name="earthhillshade",
        display_name="Global Hillshade Map",
        extension="png",
        min_zoom=0,
        max_zoom=8,
        description="Global terrain hillshade",
        japanese_name="陰影起伏図（全球版）",
        full_description="Global hillshade relief map showing terrain features worldwide.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="elevation",
    ),
    "anaglyphmap_gray": LayerConfig(
        name="anaglyphmap_gray",
        display_name="Anaglyph Gray",
        extension="png",
        min_zoom=2,
        max_zoom=16,
        description="3D terrain anaglyph (grayscale)",
        japanese_name="アナグリフ（グレー）",
        full_description="3D anaglyph terrain visualization in grayscale for red-cyan glasses.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="elevation",
    ),
    "anaglyphmap_color": LayerConfig(
        name="anaglyphmap_color",
        display_name="Anaglyph Color",
        extension="png",
        min_zoom=2,
        max_zoom=16,
        description="3D terrain anaglyph (color)",
        japanese_name="アナグリフ（カラー）",
        full_description="3D anaglyph terrain visualization in color for red-cyan glasses.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="elevation",
    ),
    "slopezone1map": LayerConfig(
        name="slopezone1map",
        display_name="Slope Zone Map (Avalanche)",
        extension="png",
        min_zoom=3,
        max_zoom=15,
        description="Slope zones for avalanche risk",
        japanese_name="全国傾斜量区分図（雪崩関連）",
        full_description="National slope zone classification map for avalanche risk assessment.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="elevation",
    ),
    # Digital Elevation Models
    "dem_png": LayerConfig(
        name="dem_png",
        display_name="DEM 10m (PNG)",
        extension="png",
        min_zoom=1,
        max_zoom=14,
        description="Digital elevation model 10m PNG",
        japanese_name="標高タイル（DEM10B PNG形式）",
        full_description="Elevation data from the fundamental geospatial information digital elevation model, "
        "rendered as color-coded PNG images for visual terrain representation.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="elevation",
    ),
    "dem5a_png": LayerConfig(
        name="dem5a_png",
        display_name="DEM 5m A (PNG)",
        extension="png",
        min_zoom=1,
        max_zoom=15,
        description="Digital elevation model 5m A PNG",
        japanese_name="標高タイル（DEM5A PNG形式）",
        full_description="High-resolution 5-meter elevation data in PNG format, providing detailed "
        "terrain visualization.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="elevation",
    ),
    "dem5b_png": LayerConfig(
        name="dem5b_png",
        display_name="DEM 5m B (PNG)",
        extension="png",
        min_zoom=1,
        max_zoom=15,
        description="Digital elevation model 5m B PNG",
        japanese_name="標高タイル（DEM5B PNG形式）",
        full_description="Alternative 5-meter elevation dataset in PNG format for areas with different "
        "survey methodologies.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="elevation",
    ),
    "dem5c_png": LayerConfig(
        name="dem5c_png",
        display_name="DEM 5m C (PNG)",
        extension="png",
        min_zoom=1,
        max_zoom=15,
        description="Digital elevation model 5m C PNG",
        japanese_name="標高タイル（DEM5C PNG形式）",
        full_description="Additional 5-meter elevation coverage in PNG format, completing nationwide "
        "topographic dataset.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="elevation",
    ),
    # Thematic Maps
    "afm": LayerConfig(
        name="afm",
        display_name="Active Fault Map",
        extension="png",
        min_zoom=11,
        max_zoom=16,
        description="Active fault lines (urban areas)",
        japanese_name="活断層図（都市圏活断層図）",
        full_description="Active fault maps for urban areas showing earthquake fault lines.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="landuse",
    ),
    "lcmfc2": LayerConfig(
        name="lcmfc2",
        display_name="Flood Control Terrain Map",
        extension="png",
        min_zoom=11,
        max_zoom=16,
        description="Terrain classification for flood control",
        japanese_name="治水地形分類図",
        full_description="Terrain classification maps for water management and flood control planning.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="landuse",
    ),
    "swale": LayerConfig(
        name="swale",
        display_name="Meiji-Period Wetlands",
        extension="png",
        min_zoom=10,
        max_zoom=16,
        description="Historical wetland areas (Meiji era)",
        japanese_name="明治期の低湿地",
        full_description="Historical wetland and low-lying areas from the Meiji period.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="landuse",
    ),
    "ndvi_250m_2012_08": LayerConfig(
        name="ndvi_250m_2012_08",
        display_name="Vegetation Index 2012",
        extension="png",
        min_zoom=2,
        max_zoom=10,
        description="National vegetation index 250m",
        japanese_name="全国植生指標データ（250m）",
        full_description="National vegetation index data at 250m resolution from August 2012.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="landuse",
    ),
    "jikizu2020_chijiki_d": LayerConfig(
        name="jikizu2020_chijiki_d",
        display_name="Magnetic Map 2020 (Declination)",
        extension="png",
        min_zoom=4,
        max_zoom=13,
        description="Magnetic declination 2020",
        japanese_name="磁気図2020.0年値（偏角）",
        full_description="Magnetic declination map for 2020.0 epoch.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="reference",
    ),
    "jikizu2020_chijiki_i": LayerConfig(
        name="jikizu2020_chijiki_i",
        display_name="Magnetic Map 2020 (Inclination)",
        extension="png",
        min_zoom=4,
        max_zoom=8,
        description="Magnetic inclination 2020",
        japanese_name="磁気図2020.0年値（伏角）",
        full_description="Magnetic inclination angle map for 2020.0 epoch.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="reference",
    ),
    "jikizu2020_chijiki_f": LayerConfig(
        name="jikizu2020_chijiki_f",
        display_name="Magnetic Map 2020 (Total Force)",
        extension="png",
        min_zoom=4,
        max_zoom=8,
        description="Total magnetic force 2020",
        japanese_name="磁気図2020.0年値（全磁力）",
        full_description="Total magnetic force map for 2020.0 epoch.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="reference",
    ),
    "jikizu2020_chijiki_h": LayerConfig(
        name="jikizu2020_chijiki_h",
        display_name="Magnetic Map 2020 (Horizontal)",
        extension="png",
        min_zoom=4,
        max_zoom=8,
        description="Horizontal magnetic component 2020",
        japanese_name="磁気図2020.0年値（水平分力）",
        full_description="Horizontal magnetic component map for 2020.0 epoch.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="reference",
    ),
    "jikizu2020_chijiki_z": LayerConfig(
        name="jikizu2020_chijiki_z",
        display_name="Magnetic Map 2020 (Vertical)",
        extension="png",
        min_zoom=4,
        max_zoom=8,
        description="Vertical magnetic component 2020",
        japanese_name="磁気図2020.0年値（鉛直分力）",
        full_description="Vertical magnetic component map for 2020.0 epoch.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="reference",
    ),
    "jikizu2015_chijiki_d": LayerConfig(
        name="jikizu2015_chijiki_d",
        display_name="Magnetic Map 2015 (Declination)",
        extension="png",
        min_zoom=4,
        max_zoom=13,
        description="Magnetic declination 2015",
        japanese_name="磁気図2015.0年値（偏角）",
        full_description="Magnetic declination map for 2015.0 epoch.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="reference",
    ),
    "jikizu2015_chijiki_i": LayerConfig(
        name="jikizu2015_chijiki_i",
        display_name="Magnetic Map 2015 (Inclination)",
        extension="png",
        min_zoom=4,
        max_zoom=8,
        description="Magnetic inclination 2015",
        japanese_name="磁気図2015.0年値（伏角）",
        full_description="Magnetic inclination angle map for 2015.0 epoch.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="reference",
    ),
    "jikizu2015_chijiki_f": LayerConfig(
        name="jikizu2015_chijiki_f",
        display_name="Magnetic Map 2015 (Total Force)",
        extension="png",
        min_zoom=4,
        max_zoom=8,
        description="Total magnetic force 2015",
        japanese_name="磁気図2015.0年値（全磁力）",
        full_description="Total magnetic force map for 2015.0 epoch.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="reference",
    ),
    "jikizu2015_chijiki_h": LayerConfig(
        name="jikizu2015_chijiki_h",
        display_name="Magnetic Map 2015 (Horizontal)",
        extension="png",
        min_zoom=4,
        max_zoom=8,
        description="Horizontal magnetic component 2015",
        japanese_name="磁気図2015.0年値（水平分力）",
        full_description="Horizontal magnetic component map for 2015.0 epoch.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="reference",
    ),
    "jikizu2015_chijiki_z": LayerConfig(
        name="jikizu2015_chijiki_z",
        display_name="Magnetic Map 2015 (Vertical)",
        extension="png",
        min_zoom=4,
        max_zoom=8,
        description="Vertical magnetic component 2015",
        japanese_name="磁気図2015.0年値（鉛直分力）",
        full_description="Vertical magnetic component map for 2015.0 epoch.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="reference",
    ),
    "jikizu_chijikid": LayerConfig(
        name="jikizu_chijikid",
        display_name="Magnetic Map 2010 (Declination)",
        extension="png",
        min_zoom=4,
        max_zoom=8,
        description="Magnetic declination 2010",
        japanese_name="磁気図2010.0年値（偏角）",
        full_description="Magnetic declination map for 2010.0 epoch.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="reference",
    ),
    "jikizu_chijikii": LayerConfig(
        name="jikizu_chijikii",
        display_name="Magnetic Map 2010 (Inclination)",
        extension="png",
        min_zoom=4,
        max_zoom=8,
        description="Magnetic inclination 2010",
        japanese_name="磁気図2010.0年値（伏角）",
        full_description="Magnetic inclination angle map for 2010.0 epoch.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="reference",
    ),
    "jikizu_chijikif": LayerConfig(
        name="jikizu_chijikif",
        display_name="Magnetic Map 2010 (Total Force)",
        extension="png",
        min_zoom=4,
        max_zoom=8,
        description="Total magnetic force 2010",
        japanese_name="磁気図2010.0年値（全磁力）",
        full_description="Total magnetic force map for 2010.0 epoch.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="reference",
    ),
    "jikizu_chijikih": LayerConfig(
        name="jikizu_chijikih",
        display_name="Magnetic Map 2010 (Horizontal)",
        extension="png",
        min_zoom=4,
        max_zoom=8,
        description="Horizontal magnetic component 2010",
        japanese_name="磁気図2010.0年値（水平分力）",
        full_description="Horizontal magnetic component map for 2010.0 epoch.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="reference",
    ),
    "jikizu_chijikiz": LayerConfig(
        name="jikizu_chijikiz",
        display_name="Magnetic Map 2010 (Vertical)",
        extension="png",
        min_zoom=4,
        max_zoom=8,
        description="Vertical magnetic component 2010",
        japanese_name="磁気図2010.0年値（鉛直分力）",
        full_description="Vertical magnetic component map for 2010.0 epoch.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="reference",
    ),
    # Forest Maps
    "rinya": LayerConfig(
        name="rinya",
        display_name="National Forest",
        extension="png",
        min_zoom=14,
        max_zoom=18,
        description="National forest aerial photos",
        japanese_name="森林（国有林）",
        full_description="Aerial photographs of national forests.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="other",
    ),
    "rinya_m": LayerConfig(
        name="rinya_m",
        display_name="Private Forest",
        extension="png",
        min_zoom=14,
        max_zoom=18,
        description="Private forest aerial photos",
        japanese_name="森林（民有林）",
        full_description="Aerial photographs of private forests.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="other",
    ),
    # Global Land Cover
    "gmld_glcnmo2": LayerConfig(
        name="gmld_glcnmo2",
        display_name="Global Land Cover",
        extension="png",
        min_zoom=0,
        max_zoom=7,
        description="Global land cover classification",
        japanese_name="土地被覆（GLCNMO）",
        full_description="Global land cover classification from GLCNMO dataset.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="other",
    ),
    "gmld_ptc2": LayerConfig(
        name="gmld_ptc2",
        display_name="Tree Cover Percentage",
        extension="png",
        min_zoom=0,
        max_zoom=7,
        description="Global tree cover percentage",
        japanese_name="植生（樹木被覆率）",
        full_description="Global vegetation coverage showing tree cover percentage.",
        info_url="https://maps.gsi.go.jp/development/ichiran.html",
        category="other",
    ),
}

# Download settings
MAX_CONCURRENT_DOWNLOADS = 8
DOWNLOAD_TIMEOUT = 30  # seconds
MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds

# Tile settings
TILE_SIZE = 256  # pixels
DEFAULT_ZOOM = 12

# UI settings
DEFAULT_MAP_CENTER = [36.5, 138.0]  # Central Japan
DEFAULT_MAP_ZOOM = 6  # Show most of Japan

# Japan region bounds for validation (approximate WMTS coverage area)
JAPAN_REGION_BOUNDS = {
    "min_lon": 122.0,
    "max_lon": 154.0,
    "min_lat": 20.0,
    "max_lat": 46.0,
}
