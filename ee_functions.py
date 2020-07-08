# Created by Caleb Bitting
import ee
import geemap
import itertools
import pandas as pd
ee.Initialize()

def line_to_point(line):
    '''Translates a list of strings in the form 'name, latitude, longitude' into a ee.Geometry.Point object with that
       name and centered on the lat, long point.'''
    line_list = line.split(',')
    identity = line_list[0]
    latlong = [float(line_list[2]), float(line_list[1])]
    return ee.Feature(ee.Geometry.Point(latlong), {'filler': identity})

def importUserSHP(path, expand=False, expand_dist=10_000):
    '''Takes a string representing the path of the FeatureCollection (can be local or on GEE serevers). If expand is passed as True, will create a buffer of expand_dist around each point in the Shapefile.'''
    if '.csv' in path:      # for local paths
        with open(path, 'r') as fp:
            headers = fp.readline()
            attribute = headers.split(',')[0]       # whatever the name header is
            csv_contents = fp.read()
        list_contents = csv_contents.split('\n')
        temp = list(map(line_to_point, list_contents))
        feature_list = [feature.set(attribute, feature.get('filler')) for feature in temp]
        shapes = ee.FeatureCollection(feature_list)
    else:
        shapes = ee.FeatureCollection(path)
    # make sure the file is expanded
    if expand:
        return shapes.map(lambda point: point.buffer(expand_dist))
    else:
        return shapes
    
def indvMonthFilter(date):
    '''Function takes one strings formated as MM-YYYY to represent the desired month of the desired year.
       Returns a tuple of format (ee.Filter object, input date).'''
    month, year = date.split('-')
    # create start date
    start_date = year + '-' + month + '-01'
    # determine last day of the month    
    if month == '2' or month == '02':
        temp_year = int(year)
        end_day = 29 if temp_year%4 == 0 else 28
    else:
        days_30 = ['4', '04', '6', '06', '9', '09', '11']
        end_day = 30 if month in days_30 else 31
    # create end date
    end_date = year + '-' + month + '-' + str(end_day)

    month.rjust(2, '0')
    date = '-'.join((month, year))
    
    return (ee.Filter.date(start_date, end_date), date)

def indvYearFilter(year):
    '''Function takes one strings formated as YYYY to represent the start and the end of a time filter.
       Returns a tuple of format (ee.Filter object, input date).'''
    # Create dates that are readable by ee.Filter.date
    start_date = year + '-01-01'
    end_date = year + '-12-31'
    
    return (ee.Filter.date(start_date, end_date), year)

def yearFilter(start, end):
    '''Function accepts no input and returns a list of ee.Filter.date objects that encompass the desired duration.
       Only works if the desired length of analysis is years.'''
    # create the range of years over which to scan
    start = int(start)
    end = int(end)
    year_range = [str(num) for num in range(start, end + 1)]
    
    # append a filter for each year to a list
    date_list = []
    for yr in year_range:
        date_list.append(indvYearFilter(yr))
    
    return date_list

def monthFilter(start, end):
    '''Function accepts no input and returns a list of ee.Filter.date objects that encompass the desired duration.
       Only works if the desired length of analysis is months.'''
    # reading inputs
    start_month, start_year = start.split('-')
    end_month, end_year = end.split('-')
    start_month = int(start_month)
    end_month = int(end_month)
    start_year = int(start_year)
    end_year = int(end_year)
    
    date_list = []
    # if the desired length of comparision is less than a year
    if start_year == end_year:
        month_list = range(start_month, end_month + 1)    # what months are actually desired
        for year, month in zip(itertools.repeat(start_year), month_list):
            target_month = str(month) + '-' + str(year)
            date_list.append(indvMonthFilter(target_month))     # make a filter for them
    else:
        # beginning year
        month_list = range(start_month, 13)
        for year, month in zip(itertools.repeat(start_year), month_list):
            target_month = str(month) + '-' + str(year)
            date_list.append(indvMonthFilter(target_month))
        # any middle years
        middle_years = range(start_year + 1, end_year)
        months_list = range(1, 13)
        middle_pairs = itertools.product(months_list, middle_years)
        middle_strings = ['-'.join(map(str, date_tuple)) for date_tuple in middle_pairs]
        for target_month in middle_strings:
            date_list.append(indvMonthFilter(target_month))
        # final year
        for year, month in zip(itertools.repeat(end_year), range(1, end_month + 1)):
            target_month = str(month) + '-' + str(year)
            date_list.append(indvMonthFilter(target_month))

    return date_list

# Translate ee.Filter.date into ee.ImageCollection
def tupleToCollection(inp_tuple, satellite_path, band_select, feature_collection):
    '''Function accepts a tuple in the form (ee.Filter.date, 'date') and returns a tuple of the form
       (ee.ImageCollection, the same date string).'''
    # unpack
    temp_filter, temp_date = inp_tuple
    # make ee.ImageCollection
    temp = ee.ImageCollection(satellite_path) \
        .filter(temp_filter) \
        .select(band_select).map(lambda image: image.clip(feature_collection)) \
        .reduce(ee.Reducer.mean()) \
        .multiply(.02)
    
    return (temp, temp_date)

def aggregateData(feature_collection, start_date, end_date, satellite_path, band_select, download_data=True):
    '''This function takes five parameters and one optional parameter. feature_collection is an ee.FeatureCollection object, start_date and end_dates are strings in the format 'MM-YYYY' or 'YYYY.' satellite_path is a string representing the path to find the satellite data in GEE. band_select is the EXACT NAME of the band over which to analyze. setting download_data to False will prevent this function from downloadng data.'''
    # check for errors
    fail_1 = '-' in start_date and '-' not in end_date
    fail_2 = '-' not in start_date and '-' in end_date
    if fail_1 or fail_2: 
        raise Exception('Check the formatting of start_date and end_date')

    # deal with ee.Filter objects
    time_analysis = 'month' if '-' in start_date else 'year'

    if start_date == end_date:
        if time_analysis == 'month':
            filter_list = [indvMonthFilter(start_date)]
        else:
            filter_list = [indvYearFilter(start_date)]
    elif time_analysis == 'month':
        filter_list = monthFilter(start_date, end_date)
    else:
        filter_list = yearFilter(start_date, end_date)
    
    # create the different collections    
    collection_map = map(tupleToCollection, filter_list, itertools.repeat(satellite_path), itertools.repeat(band_select), itertools.repeat(feature_collection))

    # download data
    if download_data:
        for collection in collection_map:
            areas, date = collection
            csv_name = date + '.csv'
            geemap.zonal_statistics(areas, feature_collection, csv_name, statistics_type='MEAN', scale=1000)
            df = pd.read_csv(csv_name)
            if time_analysis == 'month':
                df['Month'] = date
            else: df['Year'] = date
            df.to_csv(csv_name)

def test():
    countries = importUserSHP('users/ccbitt23/LaFave/TanzaniaDHS', expand=True)
    aggregateData(countries, '04-2014', '08-2014', 'MODIS/006/MOD11A1', 'LST_Day_1km')

if __name__ == '__main__':
    test()