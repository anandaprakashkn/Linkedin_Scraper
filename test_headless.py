import csv
import asyncio
import random
from playwright.async_api import async_playwright

def format_revenue(revenue_dict):
    def readable(amount):
        if amount >= 1_000_000_000:
            return f"${amount / 1_000_000_000:.0f}B"
        elif amount >= 1_000_000:
            return f"${amount / 1_000_000:.0f}M"
        elif amount >= 1_000:
            return f"${amount / 1_000:.0f}K"
        else:
            return f"${amount:.0f}"

    min_r = revenue_dict.get('estimatedMinRevenue', {})
    max_r = revenue_dict.get('estimatedMaxRevenue', {})

    min_amt = min_r.get('amount')
    max_amt = max_r.get('amount')
    unit = min_r.get('unit', '')

    if not min_amt:
        return ''

    multiplier = {'THOUSAND': 1_000, 'MILLION': 1_000_000, 'BILLION': 1_000_000_000}.get(unit, 1)

    min_val = min_amt * multiplier
    max_val = max_amt * multiplier if max_amt is not None else None

    if max_val:
        return f"{readable(min_val)} - {readable(max_val)}"
    else:
        return f"{readable(min_val)}+"

async def scrape_lead_list(session_cookie, list_url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, slow_mo=100)
        context = await browser.new_context()

        # Set LinkedIn session cookie for authentication
        await context.add_cookies([{
            'name': 'li_at',
            'value': session_cookie,
            'domain': '.linkedin.com',
            'path': '/',
            'httpOnly': True,
            'secure': True,
            'sameSite': 'Lax'
        }])

        page = await context.new_page()

        # Block images, css, and js for faster loading
        await page.route('**/*.{jpg,png,gif,svg}', lambda route: route.abort())
        await page.route('**/*.{css,js}', lambda route: route.abort())

        await page.goto(list_url)
        await page.wait_for_load_state('domcontentloaded', timeout=10000)
        await page.wait_for_timeout(random.randint(2500, 3500))

        all_leads = []
        scraped_companies = {}

        while True:
            await page.wait_for_selector('table.people-list-detail__table tbody tr')
            rows = await page.query_selector_all('table.people-list-detail__table tbody tr')

            for idx, row in enumerate(rows, 1):
                name_el = await row.query_selector('a[data-anonymize="person-name"] span')  
                name = (await name_el.inner_text()).strip() if name_el else ''

                job_title_el = await row.query_selector('div[data-anonymize="job-title"]')
                job_title = (await job_title_el.inner_text()).strip() if job_title_el else ''

                company_link_el = await row.query_selector('td.list-people-detail-header__account a[href*="/sales/company/"]')
                company_name = company_link = industry = location = revenue = employees = ''
                company_details = {'location': '', 'industry': '', 'employeeCount': '', 'revenue': ''}

                # Get sales navigator URL for profile
                sales_navigator_url_el = await row.query_selector('td.list-people-detail-header__entity a[data-anonymize="person-name"]')
                sales_navigator_url = await sales_navigator_url_el.get_attribute('href') if sales_navigator_url_el else ''

                public_linkedin_url = ''
                if sales_navigator_url:
                    profile_page = await context.new_page()
                    await profile_page.goto(f'https://www.linkedin.com{sales_navigator_url}')
                    await profile_page.wait_for_timeout(random.randint(2500, 3500))

                    try:
                        overflow_button = await profile_page.query_selector('button[aria-label*="overflow"]')
                        if overflow_button:
                            await overflow_button.click()
                            await profile_page.wait_for_timeout(random.randint(1000, 2000))

                            view_profile_link = await profile_page.query_selector('a._item_1xnv7i[href*="linkedin.com/in/"]')
                            if view_profile_link:
                                public_linkedin_url = await view_profile_link.get_attribute('href')
                    except Exception as err:
                        print(f"⚠️ Error in public profile scraping: {err}")
                    await profile_page.close()

                if company_link_el:
                    company_name_el = await company_link_el.query_selector('span[data-anonymize="company-name"]')
                    company_name = (await company_name_el.inner_text()).strip() if company_name_el else ''
                    company_link = await company_link_el.get_attribute('href')

                    if company_name:
                        if company_name in scraped_companies:
                            company_details = scraped_companies[company_name]
                        else:
                            try:
                                async with page.expect_response(
                                    lambda response: "sales-api/salesApiCompanies" in response.url and response.request.resource_type == "xhr",
                                    timeout=5000
                                ) as resp_info:
                                    await company_link_el.hover()
                                    await page.wait_for_timeout(random.randint(2000, 3000))

                                company_response = await resp_info.value
                                if company_response.ok:
                                    json_data = await company_response.json()
                                    company_details = {
                                        'location': json_data.get('location', ''),
                                        'industry': json_data.get('industry', ''),
                                        'employeeCount': json_data.get('employeeCountRange', ''),
                                        'revenue': format_revenue(json_data.get('revenueRange', {}))
                                    }
                                    scraped_companies[company_name] = company_details
                            except Exception as e:
                                print(f"⚠️ Failed to scrape company {company_name}: {e}")

                location_el = await row.query_selector('td.list-people-detail-header__geography[data-anonymize="location"]')
                location = (await location_el.inner_text()).strip() if location_el else ''

                all_leads.append({
                    'name': name,
                    'jobTitle': job_title,
                    'companyName': company_name,
                    'location': location,
                    'companyLink': f'https://www.linkedin.com{company_link}' if company_link else '',
                    'profileUrl': public_linkedin_url or (f'https://www.linkedin.com{sales_navigator_url}' if sales_navigator_url else ''),
                    'companyLocation': company_details['location'],
                    'industry': company_details['industry'],
                    'employeeCount': company_details['employeeCount'],
                    'revenue': company_details['revenue']
                })

                print(f"✅ {idx} | {name} | {job_title} |{company_name} | {company_details['industry']} | {public_linkedin_url}")

            # Updated next page button logic using provided class name
            next_button = await page.query_selector('button._next-btn_15whdx')

            if next_button and await next_button.is_enabled():
                await next_button.click()
                await page.wait_for_timeout(random.randint(3000, 4000))
                await page.wait_for_selector('table.people-list-detail__table tbody tr', timeout=10000)
            else:
                print("🏁 No more pages. Scraping completed.")
                break

        with open('leads_with_company_details.csv', 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'name', 'jobTitle', 'companyName', 'location', 'companyLink',
                'profileUrl', 'companyLocation', 'industry', 'employeeCount', 'revenue'
            ])
            writer.writeheader()
            writer.writerows(all_leads)

        print("✅ All leads and company details saved to leads_with_company_details.csv.")
        await browser.close()

async def run_scraper(session_cookie, list_url):
    await scrape_lead_list(session_cookie, list_url)

# Example usage:
# asyncio.run(run_scraper("YOUR_LINKEDIN_SESSION_COOKIE", "https://www.linkedin.com/sales/lists/your-list-url"))
