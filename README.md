# snowplow_fdw
PostgreSQL foreign data wrapper for JSON data from snowplow API.

Inspired greatly by [geofdw](https://github.com/bosth/geofdw).

# Installation

## Development
1. Install docker and docker-compose.
2. Run `docker-compose up -d --build` (if you are not running with root permissions add `sudo` in the beginning of each command)
3. Install snowplow_fdw foreign data wrapper with: `docker-compose exec postgis-db bash /scripts/dev_install.sh`
4. If you make any changes to the code, just repeat the installation
5. Run `docker ps` to find out postgis-db docker name (<postgis-db-name> in next)
6. Run `docker cp docker/pg_hba.conf snowplow_fdw_<postgis-db-name>:/etc/postgresql/12/main/`
7. Run `docker-compose exec postgis-db bash`
8. Run `chown postgres:postgres /etc/postgresql/12/main/pg_hba.conf` and `exit`
9. Restart with `docker-compose restart postgis-db`

Stop database with `docker-compose stop` and start it next time with `docker-compose start`.

## Production (Tested in Debian buster)

1. Install dependencies
    ```shell script
    # Assuming that you have postgresql and postgis installed 
    apt update
    apt install python python3 python3-dev python3-pip pgxnclient
    pip3 install setuptools
    
    # Install Multicorn for Foreign Data Wrappers
    pgxn install multicorn

    # Install plpygis for Foreign Data Wrapper support for Postgis
    pip3 install -q plpygis
    pip3 install -q requests
    ```

2. Connect to your database and enable Multicorn and pg_cron extension (for scheduling tasks)
    ```sql
    CREATE EXTENSION postgis;
    CREATE EXTENSION multicorn;
    CREATE EXTENSION IF NOT EXISTS pg_cron;
    GRANT USAGE ON SCHEMA cron TO <your username>;
    ```

3. Go to the to directory where you cloned the project and install it with:
    ```shell script
    python3 setup.py install
    ```

You may have to restart Postgresql in order to find the package (`systemctl postgresql restart` or `service postgresql restart`).

# Usage

### Creating an fdw server

```sql
CREATE SERVER dev_fdw FOREIGN DATA WRAPPER multicorn OPTIONS (wrapper 'snowplowfdw.SnowplowForeignDataWrapper');
```

### Creating a table containing unit information

Create a foreign table:
```sql
CREATE FOREIGN TABLE units_temp(
id INTEGER,
name varchar
) server dev_fdw options(
url '<url to unit list>', machines '', nrows ''
);
```

Create a table for storing the unit information:
```sql
CREATE TABLE units(
id INTEGER,
name varchar
);
```

Insert the data from foreign table to units table:
```sql
INSERT INTO units (id, name)
SELECT id, name FROM units_temp;
```

### Creating a function for updating history information about active units

Create a function called "update" under cron schema as:
```sql
declare
	temprow record;
	aa varchar(50);
BEGIN
	SET timezone = '<any timezone>';
	
	FOR temprow IN
		SELECT CAST(id as text) as idtxt FROM units
	LOOP
		DROP SERVER IF EXISTS dev_fdw CASCADE;
		DROP FOREIGN TABLE IF EXISTS table_temp;

		CREATE SERVER dev_fdw FOREIGN DATA WRAPPER multicorn OPTIONS ( wrapper 'snowplowfdw.SnowplowForeignDataWrapper' );
		
		aa := temprow.idtxt;
		
		EXECUTE format('CREATE FOREIGN TABLE table_temp(
			id varchar,
			timestamp timestamptz,
			coords varchar
			) server dev_fdw options(
			url %L, machines %L, nrows %L
					   )', '<your url>', aa, '<a number of history rows you wish to gather>'
			);
        
        -- makes sure that the same history row does not appear twice in the data_table
		with result as(
			SELECT *
			FROM table_temp l
			WHERE NOT EXISTS (
				SELECT
				FROM data_table
				WHERE  timestamp = l.timestamp)
			)
		
		INSERT INTO data_table(
			id, timestamp, coords)
		SELECT CAST(id as integer), timestamp, ('POINT' || "coords")::geography)
		FROM result;
	
	END LOOP;

END;
```

Create a table for storing the history data of all units:
```sql
CREATE TABLE datatable(
id integer,
timestamp timestamptz,
coords geography
);

SET timezone = '<any timezone>';
```

In case you wish to perform the scheduled task (created above) once in every hour (etc. 12:00, 13:00, ...),
run the following command:
```sql
SELECT cron.schedule('0 */1 * * *',  $$select cron.update()$$);
```
