-- Latest network health: the immediate operations view.
SELECT
    health_status,
    count(*) AS stations,
    round(100.0 * count(*) / sum(count(*)) OVER (), 1) AS station_pct
FROM marts.station_health
WHERE run_id = $run_id
GROUP BY health_status
ORDER BY stations DESC;

-- Stations that most need rebalancing or maintenance attention.
SELECT
    station_name,
    bikes_available,
    docks_available,
    bikes_disabled + docks_disabled AS disabled_assets,
    health_status,
    round(bike_fill_ratio, 2) AS bike_fill_ratio
FROM marts.station_health
WHERE run_id = $run_id AND health_status <> 'healthy'
ORDER BY
    CASE health_status WHEN 'offline' THEN 1 WHEN 'low_bikes' THEN 2 ELSE 3 END,
    disabled_assets DESC,
    station_name;

-- Once snapshots accumulate, this identifies persistently constrained stations.
SELECT
    station_name,
    count(*) AS snapshots,
    round(avg((health_status <> 'healthy')::INTEGER), 3) AS constrained_share,
    round(avg(bikes_available), 1) AS avg_bikes,
    round(avg(docks_available), 1) AS avg_docks
FROM marts.station_health
GROUP BY station_name
HAVING count(*) >= 3
ORDER BY constrained_share DESC, snapshots DESC
LIMIT 20;

