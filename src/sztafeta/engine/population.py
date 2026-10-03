"""Budowa populacji agentów z parametrów i mapy."""

from __future__ import annotations

import numpy as np

from sztafeta.engine.geo import points_in_polygon
from sztafeta.engine.model import AgentArrays, AgentState, CityMap, FloatArr, Params, Role


def build_population(params: Params, city: CityMap, rng: np.random.Generator) -> tuple[AgentArrays, FloatArr]:
    """Zwraca tablice agentów i ich prędkości (m/s).

    Mieszkańcy są łączeni w gospodarstwa domowe mieszkające w jednym punkcie; budynek gospodarstwa
    losujemy proporcjonalnie do wagi budynku (bloki mają większą wagę niż domy).
    """
    pop = params.population
    beh = params.behavior
    n_res = pop.n_residents
    n_cour = pop.n_couriers
    n = n_res + n_cour + 1

    # gospodarstwa domowe: rozmiar 1 + Poisson(średnia - 1), obcięty do 6
    sizes_list: list[int] = []
    total = 0
    lam = max(beh.household_mean - 1.0, 0.0)
    while total < n_res:
        batch = np.minimum(1 + rng.poisson(lam, size=max(n_res // 2, 16)), 6)
        for size in batch.tolist():
            take = min(int(size), n_res - total)
            sizes_list.append(take)
            total += take
            if total >= n_res:
                break
    sizes = np.asarray(sizes_list, dtype=np.int64)
    n_house = sizes.size
    weights = city.building_weight / city.building_weight.sum()
    house_building = rng.choice(city.buildings_xy.shape[0], size=n_house, p=weights)
    house_xy = city.buildings_xy[house_building] + rng.normal(0.0, 3.0, size=(n_house, 2))
    household_res = np.repeat(np.arange(n_house, dtype=np.int64), sizes)

    role = np.full(n, int(Role.RESIDENT), dtype=np.uint8)
    role[n_res : n_res + n_cour] = int(Role.COURIER)
    role[n - 1] = int(Role.HUB)

    has_app = np.zeros(n, dtype=np.bool_)
    has_app[:n_res] = rng.random(n_res) < beh.adoption
    has_app[n_res:] = True

    shares = np.asarray(beh.lang_shares, dtype=np.float64)
    lang = np.zeros(n, dtype=np.uint8)
    lang[:n_res] = rng.choice(shares.size, size=n_res, p=shares / shares.sum()).astype(np.uint8)

    home_xy = np.empty((n, 2), dtype=np.float64)
    home_xy[:n_res] = house_xy[household_res]
    home_xy[n_res:] = city.hub_xy
    household = np.full(n, -1, dtype=np.int64)
    household[:n_res] = household_res

    n_trolls = min(pop.n_trolls, n_res)
    if n_trolls > 0:
        trolls = np.sort(rng.choice(n_res, size=n_trolls, replace=False))
        role[trolls] = int(Role.TROLL)
        has_app[trolls] = True

    in_zone = np.zeros(n, dtype=np.bool_)
    in_zone[:n_res] = points_in_polygon(home_xy[:n_res], city.hazard_zone)

    # zgłoszenie pierwszej osoby z aplikacją w gospodarstwie obejmuje też domowników bez aplikacji
    report_persons = np.ones(n, dtype=np.uint8)
    app_res = has_app[:n_res]
    no_app_per_house = np.bincount(household_res[~app_res], minlength=n_house)
    app_idx = np.flatnonzero(app_res)
    _, first_pos = np.unique(household_res[app_idx], return_index=True)
    first_app = app_idx[first_pos]
    report_persons[first_app] = np.minimum(1 + no_app_per_house[household_res[first_app]], 255).astype(
        np.uint8
    )

    is_vehicle = np.zeros(n, dtype=np.bool_)
    n_vehicle = round(n_cour * pop.courier_vehicle_share)
    is_vehicle[n_res : n_res + n_vehicle] = True

    speed = np.zeros(n, dtype=np.float64)
    speed[:n_res] = np.clip(rng.normal(beh.walk_speed_mean, beh.walk_speed_sd, size=n_res), 0.6, 2.0)
    speed[n_res : n_res + n_cour] = pop.courier_walk_speed
    speed[is_vehicle] = pop.courier_vehicle_speed

    bat = params.battery
    battery = np.full(n, 100.0, dtype=np.float64)
    battery[:n_res] = rng.uniform(bat.start_min_pct, bat.start_max_pct, size=n_res)

    state = np.where(has_app, int(AgentState.UNINFORMED), int(AgentState.NO_APP)).astype(np.uint8)

    agents = AgentArrays(
        n=n,
        role=role,
        has_app=has_app,
        lang=lang,
        home_xy=home_xy,
        household=household,
        report_persons=report_persons,
        in_zone=in_zone,
        is_vehicle=is_vehicle,
        state=state,
        battery=battery,
        informed_t=np.full(n, np.nan),
        wom_t=np.full(n, np.nan),
        evac_start_t=np.full(n, np.nan),
        evac_done_t=np.full(n, np.nan),
    )
    return agents, speed
