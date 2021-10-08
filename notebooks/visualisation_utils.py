import pathlib
import re
from glob import glob
from typing import Union, Tuple

import cartopy
import cartopy.crs as ccrs
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr
from netCDF4 import Dataset


class HigherResPlateCarree(ccrs.PlateCarree):
    @property
    def threshold(self):
        return super().threshold / 100


def dataset_times_to_datetime(data: Dataset, times: np.ndarray):
    time_unit, year, month, day = re.match('(\w+) since (\d{4})-(\d{1,2})-(\d{1,2})',
                                           data.variables['time'].units).groups()
    return pd.to_datetime(f"{year}-{month}-{day}") + pd.to_timedelta(np.array(times), time_unit)


def get_array_from_dataset(data: Dataset, variable_str: str, range_lon: Tuple[float, float] = None,
                           range_lat: Tuple[float, float] = None,
                           time_frame: Tuple[Union[str, None], Union[str, None]] = None,
                           unit_correction=1.):
    """

    :param data: dataset, netCF4 should work
    :param range_lon: min and max longitude coordinates of specific location of interest if any (degrees east)
    :param range_lat: min and max latitude coordinates of specific location of interest if any (degrees north)
    :param time_frame: timeframe of interest as tuple or list of str, None is for the whole dataset, while None on a
    bound means no limit on this side of the time window
    :param unit_correction: if needed, to rescale the values in a desired unit
    :return: the relevant array for a given variable
    """
    long_name = [v for v in data.variables if v.startswith('lon')][0]  # can contain longitude boundaries
    lat_name = [v for v in data.variables if v.startswith('lat')][0]  # can contain latitude boundaries
    longs = data.variables[long_name][:]
    lats = data.variables[lat_name][:]
    if range_lon is not None:
        min_lon, max_lon = range_lon
        mask_long = (longs <= max_lon) & (longs >= min_lon)
        ndim_lon = mask_long.ndim
    else:
        mask_long = True
        ndim_lon = 0
    if range_lat is not None:
        min_lat, max_lat = range_lat
        mask_lat = (lats <= max_lat) & (lats >= min_lat)
    else:
        mask_lat = True
    datetimes = dataset_times_to_datetime(data, data.variables['time'][:])
    if time_frame is not None:
        min_time, max_time = time_frame
        if max_time is None:
            mask_time = (datetimes >= min_time)
        elif min_time is None:
            mask_time = (datetimes <= max_time)
        else:
            mask_time = (datetimes <= max_time) & (datetimes >= min_time)
    else:
        mask_time = True
    values = data.variables[f"{variable_str}"][:]
    values.set_fill_value(np.nan)
    values_date = np.squeeze(values.filled()[mask_time, :, :])
    if values_date.ndim > 2 and ndim_lon < 2:
        values_date_place = np.squeeze(np.squeeze(values_date[:, :, mask_long])[:, mask_lat, :]) * unit_correction
    elif values_date.ndim <= 2 and ndim_lon < 2:
        values_date_place = np.squeeze(np.squeeze(values_date[:, mask_long])[mask_lat]) * unit_correction
    else:
        mask = mask_long & mask_lat
        rows, cols = np.where(mask)
        rows = np.unique(rows)
        cols = np.unique(cols)
        values_date_place = np.squeeze(np.squeeze(values_date[:, cols])[rows]) * unit_correction

    if len(longs.shape) > 1 and len(lats.shape) > 1 and ndim_lon < 2:
        longs_place = np.squeeze(longs[:, mask_long][mask_lat])
        lats_place = np.squeeze(lats[:, mask_long][mask_lat])
    elif len(longs.shape) == 1 and len(lats.shape) == 1 and ndim_lon < 2:
        longs_place = np.squeeze(longs[mask_long])
        lats_place = np.squeeze(lats[mask_lat])
    else:
        mask = mask_long & mask_lat
        rows, cols = np.where(mask)
        rows = np.unique(rows)
        cols = np.unique(cols)
        longs_place = np.squeeze(longs[:, cols][rows])
        lats_place = np.squeeze(lats[:, cols][rows])
    datetimes = np.squeeze(np.array(datetimes)[mask_time])
    return values_date_place, longs_place, lats_place, datetimes


def plot_colormap_from_array(data: np.ndarray,
                             longitudes: np.ndarray,
                             latitudes: np.ndarray,
                             range_values_to_display=None,
                             ax=None,
                             title='',
                             unit=''):
    if ax is None:
        proj = HigherResPlateCarree()
        ax = plt.axes(projection=proj)
    ax.set_extent([longitudes.min(), longitudes.max(), latitudes.min(), latitudes.max()])
    ax.coastlines()
    ax.add_feature(cartopy.feature.BORDERS.with_scale('10m'), color='black')
    if range_values_to_display is not None:
        min_value_to_display, max_value_to_display = range_values_to_display
    else:
        min_value_to_display = data.min()
        max_value_to_display = data.max()
    c_scheme = ax.pcolormesh(longitudes, latitudes, data, transform=HigherResPlateCarree(), cmap='jet',
                             vmin=min_value_to_display, vmax=max_value_to_display)
    plt.colorbar(c_scheme, location='bottom', pad=0.05,
                 label=unit, ax=ax)

    ax.set_title(title)
    return ax


def plot_barbs_from_array(u: np.ndarray, v: np.ndarray, longitudes: np.ndarray, latitudes: np.ndarray,
                          ax=None,
                          title=''):
    if ax is None:
        proj = HigherResPlateCarree()
        ax = plt.axes(projection=proj)
    ax.set_extent([longitudes.min(), longitudes.max(), latitudes.min(), latitudes.max()])
    ax.coastlines()
    ax.add_feature(cartopy.feature.LAND, color='goldenrod')
    ax.add_feature(cartopy.feature.LAKES.with_scale('10m'), color='royalblue')
    ax.add_feature(cartopy.feature.OCEAN, color='skyblue')
    ax.add_feature(cartopy.feature.BORDERS.with_scale('10m'), color='black')
    ax.add_feature(cartopy.feature.RIVERS.with_scale('10m'), color='grey')
    ax.barbs(longitudes, latitudes, u, v,
             pivot='middle', barbcolor='navy', fill_empty=True)
    ax.set_title(title)
    return ax


def plot_wind_components_from_array(u: np.ndarray, v: np.ndarray, longitudes: np.ndarray, latitudes: np.ndarray,
                                    ax=None,
                                    title=''):
    if ax is None:
        proj = HigherResPlateCarree()
        ax = plt.axes(projection=proj)
    ax.set_extent([longitudes.min(), longitudes.max(), latitudes.min(), latitudes.max()])
    speed = np.sqrt(u * u + v * v)
    ax.coastlines()
    ax.add_feature(cartopy.feature.LAND, color='goldenrod')
    ax.add_feature(cartopy.feature.LAKES.with_scale('10m'), color='royalblue')
    ax.add_feature(cartopy.feature.OCEAN, color='skyblue')
    ax.add_feature(cartopy.feature.BORDERS.with_scale('10m'), color='black')
    ax.add_feature(cartopy.feature.RIVERS.with_scale('10m'), color='grey')
    ax.quiver(longitudes, latitudes,
              u, v, speed,
              cmap=plt.cm.autumn, transform=ccrs.PlateCarree())
    ax.set_title(title)
    return ax


def plot_colormap_from_dataset(data: Dataset, time_index: int, variable_str: str, range_lon=None, range_lat=None,
                               unit_correction=1.,
                               range_values_to_display=None,
                               ax=None):
    if ax is None:
        proj = HigherResPlateCarree()
        ax = plt.axes(projection=proj)
    interest_time = dataset_times_to_datetime(data, data.variables['time'][time_index])
    values, longs_place, lats_place, datetimes = get_array_from_dataset(data, variable_str, range_lon, range_lat,
                                                                        time_frame=(interest_time, interest_time),
                                                                        unit_correction=unit_correction)
    unit = f'{data.variables[f"{variable_str}"].units.replace("**", "^")}'
    title = f'{data.variables[f"{variable_str}"].long_name} \n {interest_time}'
    ax = plot_colormap_from_array(values, longs_place, lats_place, range_values_to_display,
                                  ax=ax, title=title, unit=unit)
    return ax


def plot_wind_components_from_dataset(data: Dataset, time_index: int, variable1_str: str, variable2_str: str,
                                      range_lon=None, range_lat=None,
                                      unit_correction=1.,
                                      ax=None):
    if ax is None:
        proj = HigherResPlateCarree()
        ax = plt.axes(projection=proj)
    interest_time = dataset_times_to_datetime(data, data.variables['time'][time_index])
    v1, longs_place, lats_place, datetimes = get_array_from_dataset(data, variable1_str, range_lon, range_lat,
                                                                    time_frame=(interest_time, interest_time),
                                                                    unit_correction=unit_correction)
    v2, _, _, _ = get_array_from_dataset(data, variable2_str, range_lon, range_lat,
                                         time_frame=(interest_time, interest_time),
                                         unit_correction=unit_correction)
    title = f'{data.variables[f"{variable1_str}"].long_name}\n {data.variables[f"{variable2_str}"].long_name} \n {interest_time}'
    ax = plot_wind_components_from_array(v1, v2, longs_place, lats_place, ax=ax,
                                         title=title)
    return ax


def plot_wind_components_from_different_datasets(d1: Dataset, d2: Dataset, time_index: int, variable1_str: str,
                                                 variable2_str: str,
                                                 range_lon=None, range_lat=None,
                                                 unit_correction=1.,
                                                 range_values_to_display=None,
                                                 ax=None):
    if ax is None:
        proj = HigherResPlateCarree()
        ax = plt.axes(projection=proj)
    interest_time = dataset_times_to_datetime(d1, d1.variables['time'][time_index])
    v1, longs_place, lats_place, datetimes = get_array_from_dataset(d1, variable1_str, range_lon, range_lat,
                                                                    time_frame=(interest_time, interest_time),
                                                                    unit_correction=unit_correction)
    v2, _, _, _ = get_array_from_dataset(d2, variable2_str, range_lon, range_lat,
                                         time_frame=(interest_time, interest_time),
                                         unit_correction=unit_correction)
    title = f'{d1.variables[f"{variable1_str}"].long_name}\n {d2.variables[f"{variable2_str}"].long_name} \n {interest_time}'
    ax = plot_wind_components_from_array(v1, v2, longs_place, lats_place, range_values_to_display, ax=ax,
                                         title=title)
    return ax


def plot_ERA5_wind_fields_timelapse(start_date, end_date, data_path, plot_path, range_lon=None, range_lat=None):
    from PIL import Image
    files = glob(f'{data_path}/*surface*.nc')
    dates = sorted([pd.to_datetime(file.split('/')[-1].split('.')[0].split('_')[0]) for file in files])
    dates = [d for d in dates if d >= start_date and d <= end_date]
    for date in dates:
        date_str = date.strftime('%Y%m%d')
        file = f'{data_path}/{date_str}_era5_surface_hourly.nc'
        data = Dataset(file, mode='r')  # read the data
        subplot_kw = {'projection': HigherResPlateCarree()}
        fig, ax = plt.subplots(ncols=1, subplot_kw=subplot_kw, figsize=(25, 12.5))
        fig.subplots_adjust(wspace=0.1, left=0.05, right=0.95)
        plot_wind_components_from_dataset(data, 0, 'u10', 'v10',
                                          range_lon=range_lon, range_lat=range_lat,
                                          ax=ax)
        plt.savefig(f'{plot_path}/{date}.png')
    images = []
    for date in dates:
        images.append(
            Image.open(f'{plot_path}/{date}.png'))
    images[0].save(f'{plot_path}/era5_timelapse.gif',
                   save_all=True, append_images=images[1:], duration=300, loop=0)


def plot_ERA5_vs_COSMO1(ERA5_data_path: str, COSMO1_data_path: str, start_date, end_date):
    from cartopy.crs import epsg
    crs_cosmo = epsg(21781)
    start_date = pd.to_datetime(start_date)
    end_date = pd.to_datetime(end_date)
    for d in pd.date_range(start_date, end_date):
        # Downloading saved inputs
        d_str = d.strftime('%Y%m%d')
        print(d_str)
        cosmo = xr.open_mfdataset(pathlib.Path(COSMO1_data_path).glob(f'{d_str}*.nc')).sel(time=d_str).isel(time=0)[
            'U_10M']
        inputs_surface = xr.open_dataset(pathlib.Path(ERA5_data_path, f'x_{d_str}.nc')).sel(
            time=d_str).isel(time=0)['u10']
        fig, (ax1, ax2) = plt.subplots(ncols=2, subplot_kw={'projection': HigherResPlateCarree()},
                                       figsize=(10, 5))
        range_long = (5.379209, 11.023753)
        range_lat = (45.497330, 48.096882)
        vmin = np.min(cosmo.__array__())
        vmax = np.max(cosmo.__array__())
        cosmo.plot(cmap='jet', ax=ax1, transform=crs_cosmo, vmin=vmin,
                   vmax=vmax,
                   cbar_kwargs={"orientation": "horizontal", "shrink": 0.7,
                                "label": "10-meter U-component (m.s-1)"})
        inputs_surface.plot(cmap='jet', ax=ax2, transform=crs_cosmo, vmin=vmin,
                            vmax=vmax,
                            cbar_kwargs={"orientation": "horizontal", "shrink": 0.7,
                                         "label": "10-meter U-component (m.s-1)"})
        ax1.set_title('COSMO-1 predictions')
        ax2.set_title('ERA5 reanalysis data')
        for ax in [ax1, ax2]:
            ax.set_extent([range_long[0], range_long[1], range_lat[0], range_lat[1]])
            ax.add_feature(cartopy.feature.BORDERS.with_scale('10m'), color='black')
        fig.tight_layout()
        return fig
