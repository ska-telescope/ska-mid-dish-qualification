from disq import logger as l
import h5py
import random
from datetime import datetime, timedelta


def main(input_file):
    test_start = datetime.utcnow()
    input_f_o = h5py.File(
        input_file,
        "r",
        libver="latest",
    )
    nodes = list(input_f_o.keys())
    logger = l.Logger()
    logger.add_nodes(nodes, 50)

    logger.start()
    node_datasets = {}
    node_start_count = {}
    node_current_count = {}
    for node in nodes:
        node_datasets[node] = {
            "SourceTimestamp": input_f_o[node]["SourceTimestamp"],
            "Value": input_f_o[node]["Value"],
        }
        node_start_count[node] = input_f_o[node]["SourceTimestamp"].len()
        node_current_count[node] = 0

    print("start count =", node_start_count)

    num_datapoints = sum(node_start_count.values())
    total_count = 0
    interval = timedelta(milliseconds=5000)
    next_print_interval = datetime.now()
    while total_count < num_datapoints:
        first_rand = random.randint(0, len(nodes) - 1)
        if node_current_count[nodes[first_rand]] < node_start_count[nodes[first_rand]]:
            timestamp = datetime.fromtimestamp(
                node_datasets[nodes[first_rand]]["SourceTimestamp"][
                    node_current_count[nodes[first_rand]]
                ]
            )
            value = node_datasets[nodes[first_rand]]["Value"][
                node_current_count[nodes[first_rand]]
            ]
            logger.queue.put(
                {
                    "name": nodes[first_rand],
                    "value": value,
                    "source_timestamp": timestamp,
                }
            )
            node_current_count[nodes[first_rand]] += 1
            total_count += 1

        if next_print_interval < datetime.utcnow():
            print(f"Put {total_count} data points in queue so far")
            next_print_interval += interval

    print("end count =", node_current_count)
    print(f"Number of datapoints in {input_file} is {num_datapoints}")
    print(f"Test put {total_count} data points in queue")
    logger.stop()
    logger.wait_for_completion()
    test_stop = datetime.utcnow()
    input_f_o.close()

    test_duration = test_stop - test_start
    print(f"Test duration: {test_duration}")


if __name__ == "__main__":
    main("30_minutes.hdf5")
