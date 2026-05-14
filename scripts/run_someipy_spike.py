from someip_gui_tool.adapters.someipy_spike import check_someipy_available, describe_spike_plan


def main() -> int:
    availability = check_someipy_available()
    print(availability.detail)
    print("Spike checklist:")
    for index, item in enumerate(describe_spike_plan(), start=1):
        print(f"{index}. {item}")
    return 0 if availability.available else 2


if __name__ == "__main__":
    raise SystemExit(main())
