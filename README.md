# ramsey

Movie critic application. Rate and keep track of what movies and shows you have seen.

## Installation

### Docker

You can install the entire application's stack using the following command:

```bash
docker compose up --build -d
```

After that you should have a web app running at `http://localhost:8000`

### Source

If you only plan on using the application you can install using the following command:

```bash
make install
```

Otherwise if you want to develop the application should use:

```bash
make install-all
```

To run the application you can simply use:

```bash
make run
```
