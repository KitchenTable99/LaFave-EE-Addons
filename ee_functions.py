# Created by Caleb Bitting
import ee
ee.Initialize()

def line_to_point(line):
    '''Translates a list of strings in the form 'name, latitude, longitude' into a ee.Geometry.Point object with that
       name and centered on the lat, long point.'''
    import ee
    ee.Initialize()
    line_list = line.split(',')
    identity = line_list[0]
    latlong = [float(line_list[2]), float(line_list[1])]
    return ee.Feature(ee.Geometry.Point(latlong), {'filler': identity})

def importUserSHP(path, expand=False, expand_dist=10_000):
    '''Takes a string representing the path of the FeatureCollection (can be local or on GEE serevers). If expand is passed as True, will create a buffer of expand_dist around each point in the Shapefile.'''
    import ee
    ee.Initialize()
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

def test():
    countries = importUserSHP('users/ccbitt23/LaFave/TanzaniaDHS', expand=True)
    print(countries.getInfo())

if __name__ == '__main__':
    test()