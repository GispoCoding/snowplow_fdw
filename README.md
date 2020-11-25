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


You have to restart PostgreSQL in order to find the package (`systemctl postgresql restart` or `service postgresql restart`).

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
url '<url to unit list>'
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

### Creating a function for updating history information of active units

Create a function called "update" under cron schema as:
```sql
declare
    temprow record;
    aa varchar(250);
    bb varchar(250);
    cc varchar(250) := '<beginning part of the url for snowplow API (before unit ID)>';
    dd varchar(250) := '<rest of the url for snowplow API (after unit ID)>';

BEGIN
	
	FOR temprow IN
		SELECT CAST(id as text) as idtxt FROM idtable WHERE last_timestamp >= current_timestamp at time zone 'Europe/Helsinki' - interval '<any time interval>'
	LOOP
		DROP SERVER IF EXISTS dev_fdw CASCADE;
		DROP FOREIGN TABLE IF EXISTS tabletemp;

		CREATE SERVER dev_fdw FOREIGN DATA WRAPPER multicorn OPTIONS ( wrapper 'snowplowfdw.SnowplowForeignDataWrapper' );
		
		aa := temprow.idtxt;
		bb := cc || aa || dd;
		
		EXECUTE format('CREATE FOREIGN TABLE tabletemp(
			id varchar,
			timestamp timestamptz,
			coords varchar,
			events varchar
			) server dev_fdw options(
			url %L
					   )', bb
			);

        -- makes sure that the same history row does not appear twice in the datatable
		with result as(
			SELECT *
			FROM tabletemp l
			WHERE NOT EXISTS (
				SELECT
				FROM datatable
				WHERE id = CAST(aa as integer) and timestamp = l.timestamp)
			)
		
		INSERT INTO datatable(
			id, timestamp, coords, events)
		SELECT CAST(id as integer), timestamp, ('POINT' || "coords")::geography, CAST(TRIM(CAST("events" as text),'['']') as text)
		FROM result;
	
	END LOOP;

END;
```

Create a table for storing the history data of all units:
```sql
CREATE TABLE datatable(
id integer,
timestamp timestamp,
coords geography,
events varchar
);
```

In case you wish to perform the scheduled task (e.g. run the update function) once in every hour (12:00, 13:00 etc.), execute the following command:
```sql
SELECT cron.schedule('0 */1 * * *',  $$select cron.update()$$);
```
