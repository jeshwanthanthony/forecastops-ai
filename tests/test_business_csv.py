import pandas as pd
import pytest

from data_utils import SalesDataError, read_business_csv, normalize_business_csv


def test_semicolon_windows_encoding_and_transaction_aggregation():
    rows = ['business_date;net_sales;note'] + [f'2026-01-{day:02d};"$1,200.50";café' for day in range(1, 29)] + ['2026-01-01;"(100.00)";refund']
    frame, preview = read_business_csv('\n'.join(rows).encode('cp1252'))
    assert preview['encoding'] == 'windows-1252'
    assert preview['delimiter'] == 'semicolon'
    data, report = normalize_business_csv(frame, 'business_date', 'net_sales')
    assert data.sales.iloc[0] == 1100.5
    assert report['duplicate_rows_aggregated'] == 1


def test_ambiguous_dates_require_selection():
    frame = pd.DataFrame({'date': [f'01/{i:02}/2026' for i in range(1,29)], 'sales':['10']*28})
    with pytest.raises(SalesDataError, match='Ambiguous'):
        normalize_business_csv(frame, 'date', 'sales')
    assert len(normalize_business_csv(frame, 'date', 'sales', date_order='mdy')[0]) == 28


def test_invalid_amount_and_empty_csv():
    with pytest.raises(SalesDataError, match='empty'):
        read_business_csv(b'')
    frame = pd.DataFrame({'date':pd.date_range('2026-01-01',periods=28).astype(str),'sales':['x']*28})
    with pytest.raises(SalesDataError, match='invalid'):
        normalize_business_csv(frame,'date','sales')
