package recording.service;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.annotation.JsonSetter;

@JsonIgnoreProperties(ignoreUnknown = true)
public class Chronicle {
    private String nomDeChronique;
    private Integer startTime;
    private Integer endTime;

    public Chronicle() {
    }

    public Chronicle(String nomDeChronique, Integer startTime, Integer endTime) {
        this.nomDeChronique = nomDeChronique;
        this.startTime = startTime;
        this.endTime = endTime;
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;

        Chronicle chronicle = (Chronicle) o;

        if (nomDeChronique != null ? !nomDeChronique.equals(chronicle.nomDeChronique) : chronicle.nomDeChronique != null)
            return false;
        if (startTime != null ? !startTime.equals(chronicle.startTime) : chronicle.startTime != null) return false;
        return endTime != null ? endTime.equals(chronicle.endTime) : chronicle.endTime == null;
    }

    @Override
    public int hashCode() {
        int result = nomDeChronique != null ? nomDeChronique.hashCode() : 0;
        result = 31 * result + (startTime != null ? startTime.hashCode() : 0);
        result = 31 * result + (endTime != null ? endTime.hashCode() : 0);
        return result;
    }

    @JsonProperty("title")
    public String getNomDeChronique() {
        return nomDeChronique;
    }

    @JsonSetter("title")
    public void setNomDeChronique(String nomDeChronique) {
        this.nomDeChronique = nomDeChronique;
    }

    public Integer getStartTime() {
        return startTime;
    }

    public void setStartTime(Integer startTime) {
        this.startTime = startTime;
    }

    @JsonSetter("time")
    public void setStartTimeFromTime(String time) {
        if (time != null && time.contains(":")) {
            String[] parts = time.split(":");
            int hour = Integer.parseInt(parts[0]);
            int minute = Integer.parseInt(parts[1]);
            int totalSeconds = hour * 3600 + minute * 60;
            // Référence théorique : La matinale commence à 07:00:00 sur France Inter
            this.startTime = totalSeconds - ChroniclesManagerService.REFERENCE_SECONDS;
        }
    }

    public Integer getEndTime() {
        return endTime;
    }

    public void setEndTime(Integer endTime) {
        this.endTime = endTime;
    }
}
