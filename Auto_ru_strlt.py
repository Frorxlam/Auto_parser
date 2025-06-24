import streamlit as st
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time
import re

# Page config
st.set_page_config(
    page_title="Парсер Auto.ru",
    page_icon="🚗",
    layout="wide"
)

st.title("🚗 Парсер автомобилей Auto.ru")
st.markdown("Введите URL с Auto.ru для парсинга объявлений")

# URL input
url_input = st.text_input(
    "Введите URL Auto.ru:",
    placeholder="https://auto.ru/cars/new/group/...",
    help="Вставьте ссылку с Auto.ru. Приложение автоматически определит новые или б/у автомобили."
)

def setup_driver():
    """Setup Selenium WebDriver"""
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--headless")  # Run in headless mode for Streamlit
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)

def parse_new_vehicles(base_url):
    """Parser for new vehicles"""
    driver = setup_driver()
    
    def parse_page(url):
        driver.get(url)

        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, "//iframe[contains(@src, 'captcha')]"))
            )
            st.warning("Обнаружена капча. При необходимости обработайте вручную.")
            return []
        except:
            pass  # No captcha found

        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'CardGroupListingItem'))
            )
        except:
            st.error("Не удалось загрузить элементы страницы")
            return []

        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')

        model_links = soup.find_all('a', class_='Link CardGroupListingItem__titleLink')
        brand_element = soup.find('h1', class_='CardGroupHeaderDesktop__title-nZZMr')
        brand_name = brand_element.text.strip().replace("Купить", "")[:-10] if brand_element else "Unknown"
        prices = soup.find_all('span', class_='OfferPriceCaption__price')
        dealers = soup.find_all('a', class_='Link CardGroupListingItemFooter__dealerName')
        specs = soup.find_all('div', class_='CardGroupListingItem__techSummary')
        stocks = soup.find_all('ul', class_='CardGroupListingItem__horizontalList')
        cities = soup.find_all('span', class_='MetroListPlace__regionName MetroListPlace_nbsp')

        data = []
        min_length = min(len(model_links), len(prices), len(dealers), len(specs), len(stocks), len(cities))
        
        for i in range(min_length):
            model_name = model_links[i].text.strip()
            price_value = prices[i].text.strip()
            dealer_value = dealers[i].text.strip()
            specs_value = ' '.join(div.get_text(strip=True) for div in specs[i].find_all('div'))
            stock_value = stocks[i].text.strip()
            city_value = cities[i].text.strip()
            data.append([brand_name, model_name, price_value, dealer_value, specs_value, stock_value, city_value])

        return data

    # Parse pages
    all_data = []
    
    # First page
    with st.spinner("Парсинг первой страницы..."):
        page_data = parse_page(base_url)
        all_data.extend(page_data)

    # Check for pagination
    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')
    pagination = soup.find_all('a', class_='Button Button_color_whiteHoverBlue Button_disabled Button_checked Button_size_s Button_type_link Button_width_default ListingPagination__page')

    if pagination:
        progress_bar = st.progress(0)
        for page_num in range(2, 11):  # Limit to 10 pages for demo
            url = f"{base_url}?page={page_num}"
            try:
                with st.spinner(f"Парсинг страницы {page_num}..."):
                    page_data = parse_page(url)
                    if not page_data:
                        break
                    all_data.extend(page_data)
                    progress_bar.progress(min(page_num / 10, 1.0))
            except Exception as e:
                st.error(f"Ошибка на странице {page_num}: {e}")
                break

    driver.quit()
    
    # Create DataFrame
    df = pd.DataFrame(all_data, columns=['Модель', 'Комплектация', 'Цена', 'Дилер', 'Спецификация', 'Наличие', 'Город'])
    
    # Parse specifications
    if not df.empty:
        df = parse_specifications(df)
        # Clean price data
        df['Цена'] = df['Цена'].str.replace(r'[^\d]', '', regex=True)
        df['Цена'] = pd.to_numeric(df['Цена'], errors='coerce')
    
    return df

def parse_used_vehicles(base_url):
    """Parser for used vehicles"""
    driver = setup_driver()
    
    def parse_page(url):
        driver.get(url)

        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, "//iframe[contains(@src, 'captcha')]"))
            )
            st.warning("Captcha detected. Please handle manually if needed.")
            return []
        except:
            pass  # No captcha found

        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'ListingItem__title'))
            )
        except:
            st.error("Failed to load page elements")
            return []

        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')

        model_blocks = soup.find_all('div', class_='ListingItem__title')
        specs_blocks = soup.find_all('div', class_='ListingItemTechSummaryDesktop ListingItem__techSummary')
        cities = soup.find_all('span', class_='MetroListPlace__regionName MetroListPlace_nbsp')
        years = soup.find_all('div', class_='ListingItem__year')
        mileages = soup.find_all('div', class_='ListingItem__kmAge')
        prices = soup.find_all('div', class_='ListingItemPrice__content')

        brand_name_tag = soup.find('h1', class_='CardGroupHeaderDesktop__title-nZZMr')
        brand_name = brand_name_tag.text.strip().replace("Купить", "")[:-10] if brand_name_tag else "Неизвестно"

        data = []
        min_length = min(len(model_blocks), len(specs_blocks), len(cities), len(years), len(mileages), len(prices))

        for i in range(min_length):
            model_name = model_blocks[i].get_text(strip=True)
            specs_value = ' '.join(div.get_text(strip=True) for div in specs_blocks[i].find_all('div'))
            city_value = cities[i].text.strip()
            year_value = years[i].text.strip()
            mileage_value = mileages[i].text.strip().replace('\xa0', ' ').replace('км', '').strip()
            price_value = prices[i].text.strip().replace('\xa0', ' ').replace('₽', '').strip()

            # Filter out high mileage (over 1000 km as per your logic)
            try:
                mileage_num = int(mileage_value.replace(' ', '').replace(',', ''))
                if mileage_num > 1000:
                    continue
            except:
                continue

            data.append([brand_name, model_name, specs_value, city_value, year_value, mileage_value, price_value])

        return data

    # Parse pages
    all_data = []
    
    # First page
    with st.spinner("Parsing first page..."):
        page_data = parse_page(base_url)
        all_data.extend(page_data)

    # Check for pagination
    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')
    pagination = soup.find_all('a', class_='Button Button_color_whiteHoverBlue Button_disabled Button_checked Button_size_s Button_type_link Button_width_default ListingPagination__page')

    if pagination:
        progress_bar = st.progress(0)
        for page_num in range(2, 11):  # Limit to 10 pages for demo
            url = f"{base_url}?page={page_num}"
            try:
                with st.spinner(f"Parsing page {page_num}..."):
                    page_data = parse_page(url)
                    if not page_data:
                        break
                    all_data.extend(page_data)
                    progress_bar.progress(min(page_num / 10, 1.0))
            except Exception as e:
                st.error(f"Error on page {page_num}: {e}")
                break

    driver.quit()
    
    # Create DataFrame
    columns = ['Марка', 'Модель', 'Спецификация', 'Город', 'Год выпуска', 'Пробег', 'Цена']
    df = pd.DataFrame(all_data, columns=columns)
    
    # Parse specifications for used vehicles
    if not df.empty:
        df = parse_used_specifications(df)
        # Clean price data
        df['Цена'] = df['Цена'].str.replace(r'[^\d]', '', regex=True)
        df['Цена'] = pd.to_numeric(df['Цена'], errors='coerce')
    
    return df

def parse_used_specifications(df):
    """Parse used vehicle specifications"""
    trans_dict = {
        'механика': 'MT',
        'механическая': 'MT',
        'вариатор': 'CVT',
        'робот': 'AMT',
        'автомат': 'AT',
        'акпп': 'AT',
        'cvt': 'CVT'
    }

    def parse_row(text):
        result = {}

        # Engine volume, power, fuel
        match = re.search(r'(\d+\.\d)\s*л.?[\s\u2009]*/[\s\u2009]*(\d+)\s*л\.с\..?/[\s\u2009]*(\w+)', text)
        if match:
            result['engine_volume'] = match.group(1)
            result['power'] = int(match.group(2))
            result['fuel_type'] = match.group(3)

        # Transmission
        for word, code in trans_dict.items():
            if re.search(rf'\b{word}\b', text, flags=re.IGNORECASE):
                result['transmission'] = code
                break
        else:
            result['transmission'] = None

        # Drive type
        if 'передний' in text:
            result['drive'] = 'FWD'
        elif 'полный' in text:
            result['drive'] = 'AWD'
        elif 'задний' in text:
            result['drive'] = 'RWD'
        else:
            result['drive'] = None

        # Color
        drive_match = re.search(r'(передний|полный|задний)\s+(\w+)', text)
        if drive_match:
            result['color'] = drive_match.group(2)

        # Base options
        base_match = re.search(r'(\d+)\s+базов\w* опц\w*', text)
        if base_match:
            result['base_options'] = int(base_match.group(1))

        # Extra options
        extra_match = re.search(r'(\d+)\s+доп\.?\s+опц\w*', text)
        if extra_match:
            result['extra_options'] = int(extra_match.group(1))

        return pd.Series(result)

    parsed = df['Спецификация'].apply(parse_row)
    # Drop 'Марка' column and concat with parsed data
    df_without_marka = df.drop(columns=['Марка']) if 'Марка' in df.columns else df
    return pd.concat([df_without_marka, parsed], axis=1)

def parse_specifications(df):
    """Parse new vehicle specifications"""
    trans_dict = {
        'механика': 'MT',
        'механическая': 'MT',
        'вариатор': 'CVT',
        'робот': 'AMT',
        'автомат': 'AT',
        'акпп': 'AT',
        'cvt': 'CVT'
    }

    fuel_dict = {
        'дизель': 'Дизель',
        'бензин': 'Бензин',
        'электро': 'Электро',
        'гибрид': 'Гибрид',
        'газ': 'Газ'
    }

    def parse_row(text):
        result = {}

        # Engine volume and power
        match = re.search(r'(\d+\.\d)\s*л.?[\s\u2009]*/[\s\u2009]*(\d+)\s*л\.с\.', text)
        if match:
            result['engine_volume'] = match.group(1)
            result['power'] = int(match.group(2))

        # Fuel type
        for key, value in fuel_dict.items():
            if key in text.lower():
                result['fuel_type'] = value
                break
        else:
            result['fuel_type'] = None

        # Transmission
        for word, code in trans_dict.items():
            if re.search(rf'\b{word}\b', text, flags=re.IGNORECASE):
                result['transmission'] = code
                break
        else:
            result['transmission'] = None

        # Drive type
        if 'передний' in text:
            result['drive'] = 'FWD'
        elif 'полный' in text:
            result['drive'] = 'AWD'
        elif 'задний' in text:
            result['drive'] = 'RWD'
        else:
            result['drive'] = None

        # Color
        drive_match = re.search(r'(передний|полный|задний)\s+(\w+)', text)
        if drive_match:
            result['color'] = drive_match.group(2)

        # Base options
        base_match = re.search(r'(\d+)\s+базов\w* опц\w*', text)
        if base_match:
            result['base_options'] = int(base_match.group(1))

        # Extra options
        extra_match = re.search(r'(\d+)\s+доп\.?\s+опц\w*', text)
        if extra_match:
            result['extra_options'] = int(extra_match.group(1))

        return pd.Series(result)

    parsed = df['Спецификация'].apply(parse_row)
    return pd.concat([df, parsed], axis=1)

def detect_parser_type(url):
    """Detect if URL is for new or used vehicles"""
    url_lower = url.lower()
    if 'new' in url_lower:
        return 'new'
    elif 'used' in url_lower:
        return 'used'
    else:
        return None

# Main app logic
if url_input:
    if not url_input.startswith('http'):
        st.error("Пожалуйста, введите корректный URL, начинающийся с http:// или https://")
    else:
        parser_type = detect_parser_type(url_input)
        
        if parser_type is None:
            st.error("Не удалось определить тип автомобилей по URL. Убедитесь, что URL содержит 'new' или 'used'")
        else:
            vehicle_type = "НОВЫЕ" if parser_type == 'new' else "Б/У"
            st.success(f"Обнаружены: **{vehicle_type}** автомобили")
            
            if st.button("🚀 Начать парсинг", type="primary"):
                try:
                    if parser_type == 'new':
                        df = parse_new_vehicles(url_input)
                    else:
                        df = parse_used_vehicles(url_input)
                    
                    if not df.empty:
                        st.success(f"Успешно спарсено {len(df)} автомобилей!")
                        
                        # Display results
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.subheader("📊 Данные")
                            st.dataframe(df, use_container_width=True)
                        
                        with col2:
                            st.subheader("📈 Статистика")
                            if 'Цена' in df.columns:
                                price_col = df['Цена'].dropna()
                                if not price_col.empty:
                                    st.metric("Средняя цена", f"{price_col.mean():,.0f} ₽")
                                    st.metric("Минимальная цена", f"{price_col.min():,.0f} ₽")
                                    st.metric("Максимальная цена", f"{price_col.max():,.0f} ₽")
                            
                            # Price range by complectation with specifications
                            complectation_col = 'Комплектация' if parser_type == 'new' else 'Модель'
                            if complectation_col in df.columns and 'Цена' in df.columns:
                                st.write("**Диапазон цен по комплектациям:**")
                                
                                # Group by complectation and get stats
                                price_stats = df.groupby(complectation_col).agg({
                                    'Цена': ['min', 'max', 'count', lambda x: x.mode().iloc[0] if not x.mode().empty else x.median()],
                                    'engine_volume': lambda x: x.mode().iloc[0] if 'engine_volume' in df.columns and not x.dropna().empty and not x.dropna().mode().empty else None,
                                    'power': lambda x: x.mode().iloc[0] if 'power' in df.columns and not x.dropna().empty and not x.dropna().mode().empty else None,
                                    'fuel_type': lambda x: x.mode().iloc[0] if 'fuel_type' in df.columns and not x.dropna().empty and not x.dropna().mode().empty else None,
                                    'transmission': lambda x: x.mode().iloc[0] if 'transmission' in df.columns and not x.dropna().empty and not x.dropna().mode().empty else None,
                                    'drive': lambda x: x.mode().iloc[0] if 'drive' in df.columns and not x.dropna().empty and not x.dropna().mode().empty else None
                                }).reset_index()
                                
                                # Flatten column names
                                price_stats.columns = [
                                    complectation_col, 'min_price', 'max_price', 'count', 'mode_price',
                                    'engine_volume', 'power', 'fuel_type', 'transmission', 'drive'
                                ]
                                
                                # Calculate potential price using the formula
                                price_stats['potential_price'] = price_stats['mode_price'].apply(
                                    lambda x: int(round((x * 0.97 / 0.85 + 250_000) / 1000) * 1000) if pd.notnull(x) else None
                                )
                                
                                price_stats = price_stats.sort_values('min_price')
                                
                                for _, row in price_stats.head(10).iterrows():  # Show top 10
                                    complectation = row[complectation_col]
                                    min_price = row['min_price']
                                    max_price = row['max_price']
                                    count = row['count']
                                    potential_price = row['potential_price']
                                    
                                    # Build specifications string
                                    specs = []
                                    if pd.notnull(row['engine_volume']):
                                        specs.append(f"{row['engine_volume']}л")
                                    if pd.notnull(row['power']):
                                        specs.append(f"{int(row['power'])}л.с.")
                                    if pd.notnull(row['fuel_type']):
                                        specs.append(str(row['fuel_type']))
                                    if pd.notnull(row['transmission']):
                                        specs.append(str(row['transmission']))
                                    if pd.notnull(row['drive']):
                                        specs.append(str(row['drive']))
                                    
                                    specs_str = " | ".join(specs) if specs else ""
                                    
                                    # Display complectation info
                                    if min_price == max_price:
                                        price_display = f"{min_price:,.0f} ₽"
                                    else:
                                        price_display = f"{min_price:,.0f} - {max_price:,.0f} ₽"
                                    
                                    potential_display = f" → **{potential_price:,.0f} ₽**" if potential_price else ""
                                    specs_display = f" ({specs_str})" if specs_str else ""
                                    
                                    st.write(f"• **{complectation}**{specs_display}: {price_display}{potential_display} ({count} шт.)")
                            
                            if 'Город' in df.columns:
                                st.write("**Топ городов:**")
                                city_counts = df['Город'].value_counts().head(5)
                                for city, count in city_counts.items():
                                    st.write(f"• {city}: {count}")
                            
                            # Additional stats for used vehicles
                            if parser_type == 'used':
                                if 'Год выпуска' in df.columns:
                                    year_col = df['Год выпуска'].dropna()
                                    if not year_col.empty:
                                        st.write("**Диапазон годов:**")
                                        st.write(f"• Самый новый: {year_col.max()}")
                                        st.write(f"• Самый старый: {year_col.min()}")
                                
                                if 'transmission' in df.columns:
                                    st.write("**Коробки передач:**")
                                    trans_counts = df['transmission'].value_counts().head(3)
                                    for trans, count in trans_counts.items():
                                        if pd.notna(trans):
                                            st.write(f"• {trans}: {count}")
                        
                        # Download button
                        csv = df.to_csv(index=False, encoding='utf-8-sig')
                        st.download_button(
                            label="📥 Скачать CSV",
                            data=csv,
                            file_name=f"auto_ru_{parser_type}_vehicles.csv",
                            mime="text/csv"
                        )
                    else:
                        st.warning("Данные не найдены. Проверьте URL или попробуйте снова.")
                        
                except Exception as e:
                    st.error(f"Ошибка во время парсинга: {str(e)}")

# Sidebar with info
with st.sidebar:
    st.header("ℹ️ Как использовать")
    st.markdown("""
    1. **Скопируйте URL** с Auto.ru
    2. **Вставьте** его в поле ввода
    3. **Нажмите** "Начать парсинг"
    4. **Скачайте** результаты в CSV
    
    **Поддерживаемые URL:**
    - Новые автомобили: URL содержащие "new"
    - Б/У автомобили: URL содержащие "used"
    """)
    
    st.header("⚡ Возможности")
    st.markdown("""
    - Автоопределение типа автомобилей
    - Обработка пагинации
    - Парсинг характеристик
    - Экспорт в CSV
    - Показ статистики
    - Расчет потенциальной цены
    """)