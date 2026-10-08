/**
 * 騰訊地圖 - 澳門寵物醫院定位
 * 使用前請先在 dashboard.html 中填入 TENCENT_MAP_KEY
 */

// 澳門寵物醫院數據
const MACAU_PET_HOSPITALS = [
    {
        id: 1,
        name: "綠十字獸醫醫院",
        nameEn: "Green Cross Veterinary Hospital",
        address: "澳門亞威羅街22號",
        addressEn: "22A Rua de Albuquerque, Macau",
        phone: "2883 7050",
        hours: "24小時營業",
        services: ["急診", "全科", "手術"],
        location: { lat: 22.1972, lng: 113.5494 }, // 氹仔
        is24Hour: true
    },
    {
        id: 2,
        name: "美國愛屋申生動物醫院",
        nameEn: "A. S. Watson Animal Hospital",
        address: "澳門孫逸仙博士大馬路544-E號大中華廣場綠湖居地下I座",
        addressEn: "Shop I, G/F, Green View, Grand China Plaza, 544-E Av. Dr. Sun Yat-Sen, Macau",
        phone: "2883 5371",
        hours: "10:00 - 20:00",
        services: ["全科", "專科", "牙科"],
        location: { lat: 22.2023, lng: 113.5442 }, // 氹仔
        is24Hour: false
    },
    {
        id: 3,
        name: "澳門寵物醫院有限公司",
        nameEn: "Macau Pet Hospital Ltd.",
        address: "澳門賈伯樂提督街3號富康花園J舖",
        addressEn: "Shop J, Fu Hong Garden, 3 Rua de Joao de Albuquerque, Macau",
        phone: "2833 2262",
        hours: "09:00 - 22:00",
        services: ["全科", "手術", "住院"],
        location: { lat: 22.1991, lng: 113.5428 }, // 高士德
        is24Hour: false
    },
    {
        id: 4,
        name: "澳栢獸醫診所",
        nameEn: "Au Pak Veterinary Clinic",
        address: "澳門東望洋新街206-212號定威大廈",
        addressEn: "206-212 Rua Nova do Guimarães, Macau",
        phone: "2835 3888",
        hours: "12:00 - 22:00",
        services: ["全科", "牙科", "皮膚科"],
        location: { lat: 22.1956, lng: 113.5489 }, // 東望洋
        is24Hour: false
    },
    {
        id: 5,
        name: "Pet Care 寵物醫療中心",
        nameEn: "Pet Care Medical Center",
        address: "澳門氹仔廣東大馬路尚匯地下",
        addressEn: "G/F, The Concord, Av. de Kwong Tung, Taipa, Macau",
        phone: "2883 3399",
        hours: "10:00 - 21:00",
        services: ["全科", "疫苗", "體檢"],
        location: { lat: 22.1536, lng: 113.5567 }, // 氹仔市區
        is24Hour: false
    },
    {
        id: 6,
        name: "愛寵獸醫診所",
        nameEn: "Love Pet Veterinary Clinic",
        address: "澳門黑沙環中街廣福安花園地下",
        addressEn: "G/F, Kwong Fook On Garden, Rua Central da Areia Preta, Macau",
        phone: "2843 2228",
        hours: "10:00 - 20:00",
        services: ["全科", "絕育", "洗牙"],
        location: { lat: 22.2056, lng: 113.5534 }, // 黑沙環
        is24Hour: false
    }
];

// 騰訊地圖實例
let map = null;
let markers = [];
let infoWindow = null;

/**
 * 初始化騰訊地圖
 * @param {string} containerId - 地圖容器ID
 * @param {string} apiKey - 騰訊地圖API Key
 */
function initHospitalMap(containerId, apiKey) {
    if (!apiKey || apiKey === 'YOUR_TENCENT_MAP_KEY') {
        console.warn('請先設置騰訊地圖 API Key');
        showMapPlaceholder(containerId);
        return;
    }

    // 動態加載騰訊地圖JS API
    const script = document.createElement('script');
    script.src = `https://map.qq.com/api/gljs?v=1.exp&key=${apiKey}`;
    script.onload = () => {
        console.log('騰訊地圖加載成功');
        createMap(containerId);
    };
    script.onerror = () => {
        console.error('騰訊地圖加載失敗');
        showMapPlaceholder(containerId);
    };
    document.head.appendChild(script);
}

/**
 * 創建地圖
 */
function createMap(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;

    try {
        // 初始化地圖，中心設為澳門
        map = new TMap.Map(container, {
            center: new TMap.LatLng(22.1987, 113.5439), // 澳門中心
            zoom: 13,
            mapStyleId: 'style1' // 默認樣式
        });

        // 創建信息窗口
        infoWindow = new TMap.InfoWindow({
            map: map,
            position: new TMap.LatLng(22.1987, 113.5439),
            offset: { x: 0, y: -40 },
            content: ''
        });
        infoWindow.close();

        // 添加醫院標記
        addHospitalMarkers();

        // 添加定位按鈕
        addLocationButton();

        console.log('地圖初始化完成');
    } catch (error) {
        console.error('地圖創建失敗:', error);
        showMapPlaceholder(containerId);
    }
}

/**
 * 添加醫院標記
 */
function addHospitalMarkers() {
    MACAU_PET_HOSPITALS.forEach(hospital => {
        const marker = new TMap.MultiMarker({
            map: map,
            styles: {
                'default': new TMap.MarkerStyle({
                    width: 30,
                    height: 40,
                    anchor: { x: 15, y: 40 },
                    color: hospital.is24Hour ? '#28a745' : '#D4A574'
                })
            },
            geometries: [{
                id: `hospital-${hospital.id}`,
                position: new TMap.LatLng(hospital.location.lat, hospital.location.lng),
                properties: hospital
            }]
        });

        // 點擊事件
        marker.on('click', (evt) => {
            const hospitalData = evt.geometry.properties;
            showHospitalInfo(hospitalData, evt.geometry.position);
        });

        markers.push(marker);
    });
}

/**
 * 顯示醫院詳情
 */
function showHospitalInfo(hospital, position) {
    // 使用側邊欄顯示詳情
    if (typeof openHospitalDrawer === 'function') {
        openHospitalDrawer(hospital);
    }

    // 同時將地圖中心移到該醫院
    if (map && position) {
        map.setCenter(position);
        map.setZoom(16);
    }
}

/**
 * 添加定位按鈕
 */
function addLocationButton() {
    const controlDiv = document.createElement('div');
    controlDiv.innerHTML = `
        <button onclick="locateUser()"
                style="position: absolute; bottom: 30px; right: 30px;
                       background: white; border: none; border-radius: 8px;
                       width: 45px; height: 45px; box-shadow: 0 2px 10px rgba(0,0,0,0.2);
                       cursor: pointer; z-index: 1000; font-size: 1.2rem; color: #D4A574;">
            <i class="fas fa-crosshairs"></i>
        </button>
    `;
    document.getElementById('hospital-map-container').appendChild(controlDiv);
}

/**
 * 定位用戶位置
 */
function locateUser() {
    if (!navigator.geolocation) {
        alert('您的瀏覽器不支持地理定位');
        return;
    }

    navigator.geolocation.getCurrentPosition(
        (position) => {
            const userLat = position.coords.latitude;
            const userLng = position.coords.longitude;

            // 檢查是否在澳門範圍內（大致）
            if (userLat < 22.1 || userLat > 22.2 || userLng < 113.5 || userLng > 113.6) {
                alert('您當前位置不在澳門境內，顯示澳門中心位置');
                map.setCenter(new TMap.LatLng(22.1987, 113.5439));
                return;
            }

            // 添加用戶位置標記
            const userMarker = new TMap.MultiMarker({
                map: map,
                styles: {
                    'user': new TMap.MarkerStyle({
                        width: 20,
                        height: 20,
                        color: '#4285F4',
                        borderColor: '#fff',
                        borderWidth: 2
                    })
                },
                geometries: [{
                    id: 'user-location',
                    styleId: 'user',
                    position: new TMap.LatLng(userLat, userLng)
                }]
            });

            map.setCenter(new TMap.LatLng(userLat, userLng));
            map.setZoom(15);

            // 找到最近的醫院
            const nearest = findNearestHospital(userLat, userLng);
            alert(`最近的寵物醫院是：${nearest.name}，距離約 ${nearest.distance.toFixed(1)} 公里`);
        },
        (error) => {
            console.error('定位失敗:', error);
            alert('無法獲取您的位置，請確保已允許定位權限');
        }
    );
}

/**
 * 計算最近的醫院
 */
function findNearestHospital(userLat, userLng) {
    let nearest = null;
    let minDistance = Infinity;

    MACAU_PET_HOSPITALS.forEach(hospital => {
        const distance = calculateDistance(
            userLat, userLng,
            hospital.location.lat, hospital.location.lng
        );
        if (distance < minDistance) {
            minDistance = distance;
            nearest = { ...hospital, distance };
        }
    });

    return nearest;
}

/**
 * 計算兩點間距離（公里）
 */
function calculateDistance(lat1, lng1, lat2, lng2) {
    const R = 6371; // 地球半徑（公里）
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLng = (lng2 - lng1) * Math.PI / 180;
    const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
              Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
              Math.sin(dLng / 2) * Math.sin(dLng / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
}

/**
 * 導航到醫院
 */
function getDirections(lat, lng) {
    // 使用騰訊地圖導航
    const url = `https://map.qq.com/nav/drive#routes/?referer=myapp&to=${lat},${lng}`;
    window.open(url, '_blank');
}

/**
 * 顯示地圖佔位符（當 API Key 未設置時）
 */
function showMapPlaceholder(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;

    container.innerHTML = `
        <div style="width: 100%; height: 100%; background: #f5f5f5; display: flex;
                    flex-direction: column; justify-content: center; align-items: center;
                    border-radius: 10px;">
            <i class="fas fa-map-marked-alt" style="font-size: 4rem; color: #ddd; margin-bottom: 20px;"></i>
            <p style="color: #999; margin-bottom: 15px;">請設置騰訊地圖 API Key 以顯示地圖</p>
            <div style="background: white; padding: 20px; border-radius: 8px; max-width: 90%;
                        box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                <h4 style="margin: 0 0 15px 0; color: #5C4B37;">
                    <i class="fas fa-hospital" style="color: #D4A574;"></i> 澳門寵物醫院列表
                </h4>
                ${MACAU_PET_HOSPITALS.map(h => `
                    <div style="padding: 12px; border-bottom: 1px solid #eee;">
                        <div style="font-weight: 600; color: #5C4B37; margin-bottom: 5px;">
                            ${h.name} ${h.is24Hour ? '<span style="color: #28a745; font-size: 0.8rem;">24H</span>' : ''}
                        </div>
                        <div style="font-size: 0.85rem; color: #666; margin-bottom: 3px;">
                            <i class="fas fa-map-marker-alt" style="color: #D4A574;"></i> ${h.address}
                        </div>
                        <div style="font-size: 0.85rem; color: #666;">
                            <i class="fas fa-phone" style="color: #D4A574;"></i> ${h.phone} |
                            <i class="fas fa-clock" style="color: #D4A574;"></i> ${h.hours}
                        </div>
                    </div>
                `).join('')}
            </div>
        </div>
    `;
}

/**
 * 顯示醫院列表（側邊欄）
 */
function renderHospitalList(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;

    container.innerHTML = MACAU_PET_HOSPITALS.map(hospital => `
        <div class="hospital-list-item" onclick="openHospitalDrawerById(${hospital.id})"
             style="padding: 15px; border-bottom: 1px solid #eee; cursor: pointer;
                    transition: background 0.3s;"
             onmouseover="this.style.background='#f9f9f9'"
             onmouseout="this.style.background='white'">
            <div style="display: flex; justify-content: space-between; align-items: start;">
                <div style="flex: 1;">
                    <h4 style="margin: 0 0 8px 0; color: #5C4B37; font-size: 1rem;">
                        ${hospital.name}
                        ${hospital.is24Hour ? '<span style="background: #28a745; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; margin-left: 8px;">24H</span>' : ''}
                    </h4>
                    <p style="margin: 5px 0; color: #666; font-size: 0.85rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                        <i class="fas fa-map-marker-alt" style="color: #D4A574; width: 18px;"></i> ${hospital.address}
                    </p>
                    <p style="margin: 5px 0; color: #666; font-size: 0.85rem;">
                        <i class="fas fa-phone" style="color: #D4A574; width: 18px;"></i> ${hospital.phone}
                    </p>
                </div>
                <i class="fas fa-chevron-right" style="color: #D4A574; margin-left: 10px; align-self: center;"></i>
            </div>
        </div>
    `).join('');
}

/**
 * 通過ID打開醫院側邊欄
 * @param {number} hospitalId - 醫院ID
 */
function openHospitalDrawerById(hospitalId) {
    const hospital = MACAU_PET_HOSPITALS.find(h => h.id === hospitalId);
    if (!hospital) return;

    // 同時聚焦地圖
    if (typeof focusHospital === 'function') {
        focusHospital(hospitalId);
    }
}

/**
 * 聚焦到特定醫院
 */
function focusHospital(hospitalId) {
    const hospital = MACAU_PET_HOSPITALS.find(h => h.id === hospitalId);
    if (!hospital) return;

    // 移到地圖中心
    if (map) {
        const position = new TMap.LatLng(hospital.location.lat, hospital.location.lng);
        map.setCenter(position);
        map.setZoom(16);
    }

    // 打開側邊欄
    if (typeof openHospitalDrawer === 'function') {
        openHospitalDrawer(hospital);
    }
}
